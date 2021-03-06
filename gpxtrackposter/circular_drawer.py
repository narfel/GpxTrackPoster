"""Draw a circular Poster."""
# Copyright 2016-2020 Florian Pigorsch & Contributors. All rights reserved.
#
# Use of this source code is governed by a MIT-style
# license that can be found in the LICENSE file.

import argparse
import calendar
import datetime
import math
import typing

import pint  # type: ignore
import svgwrite  # type: ignore

from gpxtrackposter.exceptions import PosterError
from gpxtrackposter.poster import Poster
from gpxtrackposter.track import Track
from gpxtrackposter.tracks_drawer import TracksDrawer
from gpxtrackposter.units import Units
from gpxtrackposter.value_range import ValueRange
from gpxtrackposter.xy import XY
from gpxtrackposter import utils


class CircularDrawer(TracksDrawer):
    """Draw a circular Poster for each of the Poster's tracks.

    Attributes:
        _rings: True if distance rings should be drawn, else False.
        _ring_color: Color of distance rings.

    Methods:
        create_args: Set up an argparser for circular poster options.
        fetch_args: Get args from argparser.
        draw: Draw each year on the Poster.
    """

    def __init__(self, the_poster: Poster) -> None:
        """Init the CircularDrawer with default values for _rings and _ring_color

        Note that these can be overridden via arguments when calling."""
        super().__init__(the_poster)
        self._rings = False
        self._ring_color = "darkgrey"

    def create_args(self, args_parser: argparse.ArgumentParser) -> None:
        """Add arguments to the parser"""
        group = args_parser.add_argument_group("Circular Type Options")
        group.add_argument(
            "--circular-rings",
            dest="circular_rings",
            action="store_true",
            help="Draw distance rings.",
        )
        group.add_argument(
            "--circular-ring-color",
            dest="circular_ring_color",
            metavar="COLOR",
            type=str,
            default="darkgrey",
            help="Color of distance rings.",
        )

    def fetch_args(self, args: argparse.Namespace) -> None:
        """Get arguments from the parser"""
        self._rings = args.circular_rings
        self._ring_color = args.circular_ring_color

    def draw(self, dr: svgwrite.Drawing, g: svgwrite.container.Group, size: XY, offset: XY) -> None:
        """Draw the circular Poster using distances broken down by time"""
        if self.poster.tracks is None:
            raise PosterError("No tracks to draw.")
        if self.poster.length_range_by_date is None:
            return

        years = self.poster.years.count()
        _, counts = utils.compute_grid(years, size)
        if counts is None:
            raise PosterError("Unable to compute grid.")
        count_x, count_y = counts[0], counts[1]
        x, y = 0, 0
        cell_size = size * XY(1 / count_x, 1 / count_y)
        margin = XY(4, 4)
        if count_x <= 1:
            margin.x = 0
        if count_y <= 1:
            margin.y = 0
        sub_size = cell_size - 2 * margin
        for year in self.poster.years.iter():
            g_year = dr.g(id=f"year{year}")
            g.add(g_year)
            self._draw_year(dr, g_year, sub_size, offset + margin + cell_size * XY(x, y), year)
            x += 1
            if x >= count_x:
                x = 0
                y += 1

    def _draw_year(self, dr: svgwrite.Drawing, g: svgwrite.container.Group, size: XY, offset: XY, year: int) -> None:
        min_size = min(size.x, size.y)
        outer_radius = 0.5 * min_size - 6
        radius_range = ValueRange.from_pair(outer_radius / 4, outer_radius)
        center = offset + 0.5 * size

        if self._rings:
            self._draw_rings(dr, g, center, radius_range)

        year_style = f"dominant-baseline: central; font-size:{min_size * 4.0 / 80.0}px; font-family:Arial;"
        month_style = f"font-size:{min_size * 3.0 / 80.0}px; font-family:Arial;"

        g.add(
            dr.text(
                f"{year}",
                insert=center.tuple(),
                fill=self.poster.colors["text"],
                text_anchor="middle",
                alignment_baseline="middle",
                style=year_style,
            )
        )
        df = 360.0 / (366 if calendar.isleap(year) else 365)
        day = 0
        date = datetime.date(year, 1, 1)
        while date.year == year:
            text_date = date.strftime("%Y-%m-%d")
            a1 = math.radians(day * df)
            a2 = math.radians((day + 1) * df)
            if date.day == 1:
                (_, last_day) = calendar.monthrange(date.year, date.month)
                a3 = math.radians((day + last_day - 1) * df)
                sin_a1, cos_a1 = math.sin(a1), math.cos(a1)
                sin_a3, cos_a3 = math.sin(a3), math.cos(a3)
                r1 = outer_radius + 1
                r2 = outer_radius + 6
                r3 = outer_radius + 2
                g.add(
                    dr.line(
                        start=(center + r1 * XY(sin_a1, -cos_a1)).tuple(),
                        end=(center + r2 * XY(sin_a1, -cos_a1)).tuple(),
                        stroke=self.poster.colors["text"],
                        stroke_width=0.3,
                    )
                )
                path = dr.path(
                    d=("M", center.x + r3 * sin_a1, center.y - r3 * cos_a1),
                    fill="none",
                    stroke="none",
                )
                path.push(f"a{r3},{r3} 0 0,1 {r3 * (sin_a3 - sin_a1)},{r3 * (cos_a1 - cos_a3)}")
                g.add(path)
                tpath = svgwrite.text.TextPath(
                    path, self.poster.month_name(date.month), startOffset=(0.5 * r3 * (a3 - a1))
                )
                text = dr.text(
                    "",
                    fill=self.poster.colors["text"],
                    text_anchor="middle",
                    style=month_style,
                )
                text.add(tpath)
                g.add(text)
            if text_date in self.poster.tracks_by_date:
                self._draw_circle_segment(
                    dr,
                    g,
                    self.poster.tracks_by_date[text_date],
                    a1,
                    a2,
                    radius_range,
                    center,
                )

            day += 1
            date += datetime.timedelta(1)

    def _determine_ring_distance(self, max_length: pint.quantity.Quantity) -> typing.Optional[pint.quantity.Quantity]:
        ring_distance = None
        if self.poster.units == "metric":
            unit = Units().km
        else:
            unit = Units().mile
        for distance in [1.0 * unit, 5.0 * unit, 10.0 * unit, 50.0 * unit]:
            if max_length < distance:
                continue
            ring_distance = distance
            if (max_length / distance) <= 5:
                break
        return ring_distance

    def _draw_rings(
        self, dr: svgwrite.Drawing, g: svgwrite.container.Group, center: XY, radius_range: ValueRange
    ) -> None:
        length_range = self.poster.length_range_by_date
        if not length_range.is_valid():
            return
        min_length = length_range.lower()
        max_length = length_range.upper()
        assert min_length is not None
        assert max_length is not None
        ring_distance = self._determine_ring_distance(max_length)
        if ring_distance is None:
            return
        distance = ring_distance
        while distance < max_length:
            radius = radius_range.interpolate((distance / max_length).magnitude)
            g.add(
                dr.circle(
                    center=center.tuple(),
                    r=radius,
                    stroke=self._ring_color,
                    stroke_opacity="0.2",
                    fill="none",
                    stroke_width=0.3,
                )
            )
            distance += ring_distance

    def _draw_circle_segment(
        self,
        dr: svgwrite.Drawing,
        g: svgwrite.container.Group,
        tracks: typing.List[Track],
        a1: float,
        a2: float,
        rr: ValueRange,
        center: XY,
    ) -> None:
        length = sum([t.length() for t in tracks])
        has_special = len([t for t in tracks if t.special]) > 0
        color = self.color(self.poster.length_range_by_date, length, has_special)
        max_length = self.poster.length_range_by_date.upper()
        assert max_length is not None
        r1 = rr.lower()
        assert r1 is not None
        r2 = rr.interpolate((length / max_length).magnitude)
        sin_a1, cos_a1 = math.sin(a1), math.cos(a1)
        sin_a2, cos_a2 = math.sin(a2), math.cos(a2)
        path = dr.path(
            d=("M", center.x + r1 * sin_a1, center.y - r1 * cos_a1),
            fill=color,
            stroke="none",
        )
        path.push("l", (r2 - r1) * sin_a1, (r1 - r2) * cos_a1)
        path.push(f"a{r2},{r2} 0 0,0 {r2 * (sin_a2 - sin_a1)},{r2 * (cos_a1 - cos_a2)}")
        path.push("l", (r1 - r2) * sin_a2, (r2 - r1) * cos_a2)
        date_title = str(tracks[0].start_time().date())
        str_length = utils.format_float(self.poster.m2u(length))
        path.set_desc(title=f"{date_title} {str_length} {self.poster.u()}")
        g.add(path)
