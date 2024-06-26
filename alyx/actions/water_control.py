# TODO: only work with datetimes
import csv
from datetime import datetime, date, timedelta
from dateutil.rrule import HOURLY
import functools
import io
import structlog
from operator import attrgetter, itemgetter
import os.path as op
from typing import List

from django.urls import reverse
from django.utils.html import format_html
from django.http import HttpResponse
from django.utils import timezone

from urllib.parse import urlencode

import numpy as np

logger = structlog.get_logger(__name__)


LIMIT_POINT = 0.7

PALETTE = {
    "green": "#029e07",
    "orange": "#d17526",
    "red": "#d61e3d",
    "gray": "#1c1c1c",
}


def today():
    return timezone.now()


def to_date(s):
    if isinstance(s, str):
        return datetime.strptime("%s 12:00:00" % s, "%Y-%m-%d %H:%M:%S")
    elif isinstance(s, datetime):
        return s
    elif s is None:
        return s
    raise ValueError("The date should be either a string or a datetime.")


def date_to_datetime(d):
    return datetime(d.year, d.month, d.day, 12, 0, 0)


def date_range(start_date, end_date):
    assert isinstance(start_date, datetime)
    assert isinstance(end_date, datetime)
    for n in range(int((end_date.date() - start_date.date()).days) + 1):
        yield (start_date + timedelta(n))


# Keep the tables in memory instead of reloading the CSV files.
@functools.lru_cache(maxsize=None)
def _get_table(sex):
    sex = "male" if sex == "M" else "female"
    path = op.join(op.dirname(__file__), "static/ref_weighings_%s.csv" % sex)
    with open(path, "r") as f:
        reader = csv.reader(f)
        d = {int(age): (float(m), float(s)) for age, m, s in list(reader)}
    return d


def expected_weighing_mean_std(sex, age_w):
    d = _get_table(sex)
    age_min, age_max = min(d), max(d)
    if age_w < age_min:
        return d[age_min]
    elif age_w > age_max:
        return d[age_max]
    else:
        return d[age_w]


def to_weeks(birth_date, dt):
    if not birth_date:
        logger.warning("No birth date specified!")
        return 0
    if not dt:
        return 0
    assert isinstance(birth_date, datetime)
    assert isinstance(dt, datetime)
    return (dt - birth_date).days // 7


def restrict_dates(dates, start, end, *arrs):
    assert isinstance(start, datetime)
    assert isinstance(end, datetime)
    ind = (dates >= start) & (dates <= end)
    return [dates[ind]] + [arr[ind] for arr in arrs]


def find_color(w, e, thresholds):
    """Find the color of a weight, given the expected weight and the list of thresholds."""
    for t, bgc, fgc, ls in thresholds:
        if w < e * t:
            return bgc
    return PALETTE["green"]


def return_figure(f):
    buf = io.BytesIO()
    f.savefig(buf, format="png")
    buf.seek(0)
    return HttpResponse(buf.read(), content_type="image/png")


def tzone_convert(date_t, tz):
    assert isinstance(date_t, datetime)
    try:
        date_t = timezone.make_aware(date_t, timezone.get_default_timezone(), is_dst=False)
    except ValueError:  # date is already timezone aware
        pass
    return date_t  # timezone.make_naive(date_t, tz) todo : make this depending on settings.USE_TZ


class WaterControl(object):

    water_restrictions: List
    water_administrations: List

    def __init__(
        self,
        nickname=None,
        birth_date=None,
        sex=None,
        implant_weight=None,
        subject_id=None,
        reference_weight_pct=0.0,
        zscore_weight_pct=0.0,
        timezone=timezone.get_default_timezone(),
    ):
        assert nickname, "Subject nickname not provided"
        self.nickname = nickname
        if isinstance(birth_date, date):
            birth_date = date_to_datetime(birth_date)
        self.birth_date = to_date(birth_date)
        assert self.birth_date is None or isinstance(self.birth_date, datetime)
        self.sex = sex
        self.implant_weight = implant_weight or 0.0
        self.subject_id = subject_id
        self.water_restrictions = []
        self.water_administrations = []
        self.weighings = []
        self.reference_weighing = None
        self.reference_weight_pct = reference_weight_pct
        self.zscore_weight_pct = zscore_weight_pct
        self.thresholds = []
        self.timezone = timezone

    def today(self):
        """The date at the timezone of the current subject."""
        return tzone_convert(today(), self.timezone)

    def restriction_end_date(self, water_restriction_instance):
        wr_starts = [start for start, _, _ in self.water_restrictions]
        selected_wr_index = wr_starts.index(water_restriction_instance.start_time)

        return (
            self.water_restrictions[selected_wr_index][1]
            if self.water_restrictions[selected_wr_index][1]
            else self.today()
        )

    def first_date(self):
        dwa = dwe = None
        if self.water_administrations:
            dwa = min(d for d, _, _ in self.water_administrations)
        if self.weighings:
            dwe = min(d for d, _ in self.weighings)
        if not dwa and not dwe:
            return self.birth_date
        elif dwa and dwe:
            return min(dwa, dwe)
        elif dwa:
            return dwa
        elif dwe:
            return dwe
        assert 0

    def _check_water_restrictions(self):
        """Make sure all past water restrictions (except the current one) are finished."""
        last_date = None
        for s, e, wr in self.water_restrictions[:-1]:
            if e is None:
                logger.warning(
                    "The water restriction started on %s for %s not finished!",
                    s,
                    self.nickname,
                )
            # Ensure the water restrictions are ordered.
            if last_date:
                assert s >= last_date
            last_date = s

    def add_water_restriction(self, start_date=None, end_date=None, reference_weight=None):
        """Add a new water restriction."""
        assert isinstance(start_date, datetime)
        assert end_date is None or isinstance(end_date, datetime)
        self._check_water_restrictions()
        self.water_restrictions.append((start_date, end_date, reference_weight))

    def end_current_water_restriction(self):
        """If the mouse is under water restriction, end it."""
        self._check_water_restrictions()
        if not self.water_restrictions:
            return
        s, e, wr = self.water_restrictions[-1]
        if e is not None:
            logger.warning("The mouse %s is not currently under water restriction.", self.nickname)
            return
        self.water_restrictions[-1] = (s, self.today(), wr)

    def current_water_restriction(self):
        """Return the date of the current water restriction if there is one, or None."""
        if not self.water_restrictions:
            return None
        s, e, wr = self.water_restrictions[-1]
        return s if e is None else None

    def is_water_restricted(self, date=None):
        """Return whether the subject is currently under water restriction.

        This means the latest water restriction has no end date.

        """
        return self.water_restriction_at(date=date) is not None

    def water_restriction_at(self, date=None):
        """If the subject was under water restriction at the specified date, return
        the start of that water restriction."""
        date = date or self.today()
        water_restrictions_before = [(s, e, rw) for (s, e, rw) in self.water_restrictions if s.date() <= date.date()]
        if not water_restrictions_before:
            return
        s, e, rw = water_restrictions_before[-1]
        # Return None if the mouse was not under water restriction at the specified date.
        if e is not None and date > e:
            return None
        assert e is None or e >= date
        assert s.date() <= date.date()
        return s

    def add_weighing(self, date, weighing):
        """Add a weighing."""
        self.weighings.append((tzone_convert(date, self.timezone), weighing))

    def set_reference_weight(self, date, weight):
        """Set a non-default reference weight."""
        self.reference_weighing = (date, weight)

    def add_water_administration(self, date, volume, session=None):
        self.water_administrations.append((tzone_convert(date, self.timezone), volume, session))

    def add_threshold(self, percentage=None, bgcolor=None, fgcolor=None, line_style=None):
        """Add a threshold for the plot."""
        line_style = line_style or "-"
        self.thresholds.append((percentage, bgcolor, fgcolor, line_style))
        self.thresholds[:] = sorted(self.thresholds, key=itemgetter(0))

    def reference_weighing_at(self, date=None):
        """Return a tuple (date, weight) the reference weighing at the specified date, or today."""
        if self.reference_weighing and (date is None or date >= self.reference_weighing[0]):
            return self.reference_weighing
        date = date or self.today()
        assert isinstance(date, datetime)
        wr = self.water_restriction_at(date)
        if not wr:
            return
        # get the reference weight of the valid water restriction at the time
        ref_weight = [(d, w) for d, e, w in self.water_restrictions if d == wr][0]
        # if this one is zero, return the last weight before
        if ref_weight[1] == 0:
            ref_weight = self.last_weighing_before(wr)
        return ref_weight

    def reference_weight(self, date=None):
        """Return the reference weight at a given date."""
        rw = self.reference_weighing_at(date=date)
        if rw:
            return rw[1]
        return 0.0

    def last_weighing_before(self, date=None):
        """Return the last known weight of the subject before the specified date."""
        date = date or self.today()
        assert isinstance(date, datetime)
        # Sort the weighings.
        self.weighings[:] = sorted(self.weighings, key=itemgetter(0))
        weighings_before = [(d, w) for (d, w) in self.weighings if d.date() <= date.date()]
        if weighings_before:
            return weighings_before[-1]

    def weighing_at(self, date=None):
        """Return the weight of the subject at the specified date."""
        date = date or self.today()
        assert isinstance(date, datetime)
        weighings_at = [(d, w) for (d, w) in self.weighings if d.date() == date.date()]
        return weighings_at[0][1] if weighings_at else None

    def weight(self, date=None):
        """Return the last known weight at the given date"""
        cw = self.last_weighing_before(date=date)
        return cw[1] if cw else 0

    def expected_weight(self, date=None):
        """Expected weight of the mouse at the specified date,
        either the reference weight
        if the reference_weight_pct is >0,
        or the zscore weight."""
        # pct_sum = self.reference_weight_pct #+ self.zscore_weight_pct
        # if pct_sum == 0:
        if self.reference_weight_pct == 0:
            return 0

        return self.implantless_weight_percentage(self.reference_weight(date=date), self.reference_weight_pct)

    def percentage_weight(self, date=None):
        """Percentage of the weight relative to the reference weight.
        Expected weight is the reference weight or the zscore weight depending on the water
        restriction fields.

        Note: a percentage of 0 means that the expected weight was not available.

        """
        date = date or self.today()
        iw = self.implant_weight or 0.0
        w = self.weight(date=date)
        e = self.reference_weight(date=date)
        return 100 * (w - iw) / (e - iw) if (e - iw) > 0 else 0.0

    def implantless_weight_percentage(self, weight, percentage: float = 1):
        iw = self.implant_weight or 0.0
        return (percentage * (weight - iw)) + iw

    def percentage_weight_html(self, date=None):
        status = self.weight_status(date=date)
        pct_wei = self.percentage_weight(date=date)

        # Determine the color.
        colour_code = PALETTE["green"]  # status = 0 : all good
        if not self.is_water_restricted(date=date):
            colour_code = PALETTE["gray"]

        elif status == 1:  # orange colour code for reminders
            colour_code = PALETTE["orange"]

        elif status == 2:  # red colour code for errors
            colour_code = PALETTE["red"]

        if pct_wei == 0:
            return "-"

        else:
            url = reverse("water-history", kwargs={"subject_id": self.subject_id})
            return format_html(f'<b><a href="{url}" style="color: {colour_code};">{pct_wei:2.1f}%</a></b>')

    def remaining_water_html(self, date=None):
        from subjects.models import Subject

        colour_code = PALETTE["green"]  # all is good, green

        remaining_water = self.remaining_water(date=date)

        # mouse still needs more water today, red, to not forget it
        if remaining_water > 0:
            colour_code = PALETTE["red"]

        # mouse recieved too much water, orange
        if remaining_water < 0:
            colour_code = PALETTE["orange"]

        subject = Subject.objects.get(id=self.subject_id)
        wrs = subject.water_administrations.filter(date_time__date=date.today())
        if wrs.exists():
            url = reverse(
                "admin:actions_wateradministration_change",
                args=(wrs.first().id,),
            )
        else:
            url = reverse("admin:actions_wateradministration_add")
            query_string = urlencode({"subject": self.nickname, "water_administered": remaining_water})
            url = f"{url}?{query_string}"

        return format_html(f'<b><a href="{url}" style="color: {colour_code};">{remaining_water :2.1f}</a></b>')

    def min_weight(self, date=None):
        """Minimum weight for the mouse."""
        return self.implantless_weight_percentage(self.reference_weight(date=date), LIMIT_POINT)

    def min_percentage(self, date=None):
        return self.thresholds[-1][0] * 100

    def last_water_administration_at(self, date=None):
        """Return the last known water administration of the subject before the specified date."""
        date = date or self.today()
        # Sort the water administrations.
        self.water_administrations[:] = sorted(self.water_administrations, key=itemgetter(0))
        wa_before = [(d, w, h) for (d, w, h) in self.water_administrations if d <= date]
        if wa_before:
            return wa_before[-1]

    def expected_weight_range(self, date=None):
        min_wdisp = self.implantless_weight_percentage(
            self.reference_weight(date=date),
            self.reference_weight_pct + self.zscore_weight_pct,
        )

        max_wdisp = self.implantless_weight_percentage(
            self.reference_weight(date=date),
            self.reference_weight_pct - self.zscore_weight_pct,
        )

        return min_wdisp, max_wdisp

    def expected_water(self, date=None):
        """Return the expected water for the specified date."""
        date = date or self.today()
        assert isinstance(date, datetime)

        weight = self.last_weighing_before(date=date)
        weight = weight[1] if weight else 0.0
        expected_weight = self.expected_weight(date=date) or 0.0
        MINIMUM_DAILY_WATER_INTAKE = 0.500  # mL
        MAXIMUM_DAILY_WATER_INTAKE = 1.200  # mL

        water_intake_estimation = (expected_weight - weight) * 1.5

        if water_intake_estimation > MAXIMUM_DAILY_WATER_INTAKE:
            return MAXIMUM_DAILY_WATER_INTAKE
        if water_intake_estimation < MINIMUM_DAILY_WATER_INTAKE:
            return MINIMUM_DAILY_WATER_INTAKE
        return water_intake_estimation

    def given_water(self, date=None, has_session=None):
        """Return the amount of water given at a specified date."""
        date = date or self.today()
        assert isinstance(date, datetime)
        totw = 0
        for d, w, ses in self.water_administrations:
            if d.date() != date.date() or w is None:
                continue
            if has_session is None:
                totw += w
            elif has_session and ses:
                totw += w
            elif not has_session and not ses:
                totw += w
        return totw

    def given_water_reward(self, date=None):
        """Amount of water given at the specified date as part of a session."""
        return self.given_water(date=date, has_session=True)

    def given_water_supplement(self, date=None):
        """Amount of water given at the specified date not during a session."""
        return self.given_water(date=date, has_session=False)

    def given_water_total(self, date=None):
        """Total amount of water given at the specified date."""
        return self.given_water(date=date)

    def remaining_water(self, date=None):
        """Amount of water that remains to be given at the specified date."""
        date = date or self.today()
        return self.expected_water(date=date) - self.given_water(date=date)

    def excess_water(self, date=None):
        """Amount of water that was given in excess at the specified date."""
        return -self.remaining_water(date=date)

    _columns = (
        "date",
        "weight",
        "weighing_at",
        "reference_weight",
        "expected_weight",
        "min_weight",
        "percentage_weight",
        "given_water_reward",
        "given_water_supplement",
        "given_water_total",
        "expected_water",
        "excess_water",
        "is_water_restricted",
    )

    def weight_status(self, date=None):
        w = self.weighing_at(date=date)
        min_wdisp, max_wdisp = self.expected_weight_range(date=date)

        # edge case
        if w is None or w <= 0:
            return 0

        # we are below the limit point !!! stop water restriction
        elif w < self.min_weight(date=date):
            return 2

        # either mouse is too far from the expected weight, (too heavy, too thin) or we miss giving it water yet
        elif w > max_wdisp or w < min_wdisp:
            return 1

        return 0  # all is well

    def to_jsonable(self, start_date=None, end_date=None):
        start_date = to_date(start_date) if start_date else self.first_date()
        end_date = to_date(end_date) if end_date else self.today()
        out = []
        for d in date_range(start_date, end_date):
            # do not show date rows where animal is either not water restricted or wight is not present that day
            # if not self.is_water_restricted(d):
            #    continue
            if self.weighing_at(d) is None:
                continue
            obj = {}
            for col in self._columns:
                if col == "date":
                    obj["date"] = d.date()
                else:
                    obj[col] = getattr(self, col)(date=d)
            out.append(obj)
        # return json.dumps(out, cls=DjangoJSONEncoder)
        return out

    def plot(self, start=None, end=None):
        import matplotlib

        matplotlib.use("AGG")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mpld
        from matplotlib import dates as mdates

        f, ax = plt.subplots(1, 1, figsize=(8, 3))

        iw = self.implant_weight or 0.0

        # Data arrays.
        if self.weighings:
            self.weighings[:] = sorted(self.weighings, key=itemgetter(0))
            weighing_dates, weights = zip(*self.weighings)
            weighing_dates = np.array(weighing_dates, dtype=datetime)
            logger.warning(f"weighing_dates = {weighing_dates}")
            weights = np.array(weights, dtype=np.float64)
            start = start or weighing_dates.min()
            end = end or weighing_dates.max()
            logger.warning(f"start  = {start}")
            logger.warning(f"end  = {end}")
            expected_weights = np.array(
                [self.expected_weight(date) for date in weighing_dates],
                dtype=np.float64,
            )
            reference_weights = np.array(
                [self.reference_weight(date) for date in weighing_dates],
                dtype=np.float64,
            )
        else:
            return HttpResponse("There is not weighings for that subject.")

        # spans is a list of pairs (date, color) where there are changes of background colors.
        for start_wr, end_wr, ref_weight in self.water_restrictions:
            end_wr = end_wr or end
            # Get the dates and weights for the current water restriction.

            ds, ws, es, rw = restrict_dates(
                weighing_dates,
                start_wr,
                end_wr,
                weights,
                expected_weights,
                reference_weights,
            )
            logger.warning(f"datestring = {ds}")
            # Plot background colors.
            spans = [(start_wr, None)]

            ds = np.append(np.array([start_wr]), ds)
            ws = np.append(np.array([ref_weight]), ws)

            # zw = np.append(zw[0], zw)
            rw = np.append(rw[0], rw)

            min_wdisp, max_wdisp = self.expected_weight_range(date=start_wr)

            logger.warning(f"start_wr = {start_wr}")
            logger.warning(f"ref_weight = {ref_weight}")

            ax.plot(
                start_wr,
                ref_weight,
                marker="*",
                color="blue",
                lw=0,
                markersize=15,
                zorder=3,
            )

            # Plot weight thresholds.
            for perc, _, fgc, ls in self.thresholds:
                trsh = [self.implantless_weight_percentage(ref_weight, perc) for ref_weight in rw]
                ax.plot(ds, trsh, ls, color=fgc, lw=2)

            logger.warning(f"min_wdisp = {min_wdisp}, max_wdisp = {max_wdisp}")

            ax.axhspan(min_wdisp, max_wdisp, facecolor="green", zorder=0, alpha=0.3)

            # Plot weights.
            ax.plot(ds, ws, "-ok", lw=2, zorder=2)

        # Axes and legends.
        # ax.set_xlim(start, end)
        eq = f"target weight = {int(self.reference_weight_pct*100)}% of ref +/- {int(self.zscore_weight_pct*100)}%"
        # ax.set_xticklabels(ax.get_xticks(), rotation=20)
        ax.set_title("Weighings for %s (%s)" % (self.nickname, eq))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.set_xlabel("Date")
        ax.set_ylabel("Weight (g)")
        leg = ["ref weight"] + ["%d%%" % (100 * t[0]) for t in self.thresholds] + ["target weight"]
        ax.legend(leg, loc="center right", bbox_to_anchor=(1.25, 0.5))
        ax.grid(True)
        f.autofmt_xdate()
        f.tight_layout()
        return return_figure(f)


def water_control(subject):
    assert subject is not None
    lab = subject.lab

    # By default, if there is only one lab, use it for the subject.
    if lab is None:
        logger.info(
            "Subject %s has no lab, no reference weight percentages considered.",
            subject,
        )
        rw_pct = zw_pct = 0
    else:
        rw_pct = lab.reference_weight_pct
        zw_pct = lab.zscore_weight_pct

    # Create the WaterControl instance.
    wc = WaterControl(
        nickname=subject.nickname,
        birth_date=subject.birth_date,
        sex=subject.sex,
        reference_weight_pct=rw_pct,
        zscore_weight_pct=zw_pct,
        timezone=subject.timezone(),
        subject_id=subject.id,
        implant_weight=subject.implant_weight,
    )

    wc.add_threshold(percentage=LIMIT_POINT, fgcolor=PALETTE["red"])
    wc.add_threshold(
        percentage=rw_pct,
        fgcolor=PALETTE["green"],
        line_style="--",
    )

    # Water restrictions.
    wrs = sorted(list(subject.actions_waterrestrictions.all()), key=attrgetter("start_time"))

    # Reference weight.
    last_wr = wrs[-1] if wrs else None
    if last_wr and last_wr.reference_weight:
        wc.set_reference_weight(last_wr.start_time, last_wr.reference_weight)

    for wr in wrs:
        wc.add_water_restriction(wr.start_time, wr.end_time, wr.reference_weight)

    # Water administrations.
    was = sorted(list(subject.water_administrations.all()), key=attrgetter("date_time"))
    for wa in was:
        wc.add_water_administration(wa.date_time, wa.water_administered, session=wa.session_id)

    # Weighings
    ws = sorted(list(subject.weighings.all()), key=attrgetter("date_time"))
    for w in ws:
        wc.add_weighing(w.date_time, w.weight)

    return wc
