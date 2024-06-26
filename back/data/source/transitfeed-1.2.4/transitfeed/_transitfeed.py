#!/usr/bin/python2.5

# Copyright (C) 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Easy interface for handling a Google Transit Feed file.

Do not import this module directly. Thanks to __init__.py you should do
something like:

  import transitfeed
  schedule = transitfeed.Schedule()
  ...

This module is a library to help you create, read and write Google
Transit Feed files. Refer to the feed specification, available at
http://code.google.com/transit/spec/transit_feed_specification.htm, for a
complete description how the transit feed represents a transit schedule. This
library supports all required parts of the specification but does not yet
support all optional parts. Patches welcome!

The specification describes several tables such as stops, routes and trips.
In a feed file these are stored as comma separeted value files. This library
represents each row of these tables with a single Python object. This object has
attributes for each value on the row. For example, schedule.AddStop returns a
Stop object which has attributes such as stop_lat and stop_name.

  Schedule: Central object of the parser
  GenericGTFSObject: A base class for each of the objects below
  Route: Represents a single route
  Trip: Represents a single trip
  Stop: Represents a single stop
  ServicePeriod: Represents a single service, a set of dates
  Agency: Represents the agency in this feed
  Transfer: Represents a single transfer rule
  TimeToSecondsSinceMidnight(): Convert HH:MM:SS into seconds since midnight.
  FormatSecondsSinceMidnight(s): Formats number of seconds past midnight into a string
"""

# TODO: Preserve arbitrary columns?

import bisect
import cStringIO as StringIO
import codecs
from transitfeed.util import defaultdict
import csv
import datetime
import logging
import math
import os
import random
try:
  import sqlite3 as sqlite
except ImportError:
  from pysqlite2 import dbapi2 as sqlite
import re
import tempfile
import time
import warnings
# Objects in a schedule (Route, Trip, etc) should not keep a strong reference
# to the Schedule object to avoid a reference cycle. Schedule needs to use
# __del__ to cleanup its temporary file. The garbage collector can't handle
# reference cycles containing objects with custom cleanup code.
import weakref
import zipfile

OUTPUT_ENCODING = 'utf-8'
MAX_DISTANCE_FROM_STOP_TO_SHAPE = 1000
MAX_DISTANCE_BETWEEN_STOP_AND_PARENT_STATION_WARNING = 100.0
MAX_DISTANCE_BETWEEN_STOP_AND_PARENT_STATION_ERROR = 1000.0

__version__ = '1.2.4'


def EncodeUnicode(text):
  """
  Optionally encode text and return it. The result should be safe to print.
  """
  if type(text) == type(u''):
    return text.encode(OUTPUT_ENCODING)
  else:
    return text


# These are used to distinguish between errors (not allowed by the spec)
# and warnings (not recommended) when reporting issues.
TYPE_ERROR = 0
TYPE_WARNING = 1


class ProblemReporterBase:
  """Base class for problem reporters. Tracks the current context and creates
  an exception object for each problem. Subclasses must implement
  _Report(self, e)"""

  def __init__(self):
    self.ClearContext()

  def ClearContext(self):
    """Clear any previous context."""
    self._context = None

  def SetFileContext(self, file_name, row_num, row, headers):
    """Save the current context to be output with any errors.

    Args:
      file_name: string
      row_num: int
      row: list of strings
      headers: list of column headers, its order corresponding to row's
    """
    self._context = (file_name, row_num, row, headers)

  def FeedNotFound(self, feed_name, context=None):
    e = FeedNotFound(feed_name=feed_name, context=context,
                     context2=self._context)
    self._Report(e)

  def UnknownFormat(self, feed_name, context=None):
    e = UnknownFormat(feed_name=feed_name, context=context,
                      context2=self._context)
    self._Report(e)

  def FileFormat(self, problem, context=None):
    e = FileFormat(problem=problem, context=context,
                   context2=self._context)
    self._Report(e)

  def MissingFile(self, file_name, context=None):
    e = MissingFile(file_name=file_name, context=context,
                    context2=self._context)
    self._Report(e)

  def UnknownFile(self, file_name, context=None):
    e = UnknownFile(file_name=file_name, context=context,
                  context2=self._context, type=TYPE_WARNING)
    self._Report(e)

  def EmptyFile(self, file_name, context=None):
    e = EmptyFile(file_name=file_name, context=context,
                  context2=self._context)
    self._Report(e)

  def MissingColumn(self, file_name, column_name, context=None):
    e = MissingColumn(file_name=file_name, column_name=column_name,
                      context=context, context2=self._context)
    self._Report(e)

  def UnrecognizedColumn(self, file_name, column_name, context=None):
    e = UnrecognizedColumn(file_name=file_name, column_name=column_name,
                           context=context, context2=self._context,
                           type=TYPE_WARNING)
    self._Report(e)

  def CsvSyntax(self, description=None, context=None, type=TYPE_ERROR):
    e = CsvSyntax(description=description, context=context,
                  context2=self._context, type=type)
    self._Report(e)

  def DuplicateColumn(self, file_name, header, count, type=TYPE_ERROR, 
                      context=None):
    e = DuplicateColumn(file_name=file_name,
                        header=header,
                        count=count,
                        type=type,
                        context=context,
                        context2=self._context)
    self._Report(e)

  def MissingValue(self, column_name, reason=None, context=None):
    e = MissingValue(column_name=column_name, reason=reason, context=context,
                     context2=self._context)
    self._Report(e)

  def InvalidValue(self, column_name, value, reason=None, context=None,
                   type=TYPE_ERROR):
    e = InvalidValue(column_name=column_name, value=value, reason=reason,
                     context=context, context2=self._context, type=type)
    self._Report(e)

  def DuplicateID(self, column_names, values, context=None, type=TYPE_ERROR):
    if isinstance(column_names, tuple):
      column_names = '(' + ', '.join(column_names) + ')'
    if isinstance(values, tuple):
      values = '(' + ', '.join(values) + ')'
    e = DuplicateID(column_name=column_names, value=values,
                    context=context, context2=self._context, type=type)
    self._Report(e)

  def UnusedStop(self, stop_id, stop_name, context=None):
    e = UnusedStop(stop_id=stop_id, stop_name=stop_name,
                   context=context, context2=self._context, type=TYPE_WARNING)
    self._Report(e)

  def UsedStation(self, stop_id, stop_name, context=None):
    e = UsedStation(stop_id=stop_id, stop_name=stop_name,
                    context=context, context2=self._context, type=TYPE_ERROR)
    self._Report(e)

  def StopTooFarFromParentStation(self, stop_id, stop_name, parent_stop_id,
                                  parent_stop_name, distance,
                                  type=TYPE_WARNING, context=None):
    e = StopTooFarFromParentStation(
        stop_id=stop_id, stop_name=stop_name,
        parent_stop_id=parent_stop_id,
        parent_stop_name=parent_stop_name, distance=distance,
        context=context, context2=self._context, type=type)
    self._Report(e)

  def StopsTooClose(self, stop_name_a, stop_id_a, stop_name_b, stop_id_b,
                    distance, type=TYPE_WARNING, context=None):
    e = StopsTooClose(
        stop_name_a=stop_name_a, stop_id_a=stop_id_a, stop_name_b=stop_name_b,
        stop_id_b=stop_id_b, distance=distance, context=context,
        context2=self._context, type=type)
    self._Report(e)

  def StationsTooClose(self, stop_name_a, stop_id_a, stop_name_b, stop_id_b,
                       distance, type=TYPE_WARNING, context=None):
    e = StationsTooClose(
        stop_name_a=stop_name_a, stop_id_a=stop_id_a, stop_name_b=stop_name_b,
        stop_id_b=stop_id_b, distance=distance, context=context,
        context2=self._context, type=type)
    self._Report(e)

  def DifferentStationTooClose(self, stop_name, stop_id,
                               station_stop_name, station_stop_id,
                               distance, type=TYPE_WARNING, context=None):
    e = DifferentStationTooClose(
        stop_name=stop_name, stop_id=stop_id,
        station_stop_name=station_stop_name, station_stop_id=station_stop_id,
        distance=distance, context=context, context2=self._context, type=type)
    self._Report(e)

  def StopTooFarFromShapeWithDistTraveled(self, trip_id, stop_name, stop_id,
                                          shape_dist_traveled, shape_id,
                                          distance, max_distance,
                                          type=TYPE_WARNING):
    e = StopTooFarFromShapeWithDistTraveled(
        trip_id=trip_id, stop_name=stop_name, stop_id=stop_id,
        shape_dist_traveled=shape_dist_traveled, shape_id=shape_id,
        distance=distance, max_distance=max_distance, type=type)
    self._Report(e)

  def ExpirationDate(self, expiration, context=None):
    e = ExpirationDate(expiration=expiration, context=context,
                       context2=self._context, type=TYPE_WARNING)
    self._Report(e)

  def FutureService(self, start_date, context=None):
    e = FutureService(start_date=start_date, context=context,
                      context2=self._context, type=TYPE_WARNING)
    self._Report(e)

  def InvalidLineEnd(self, bad_line_end, context=None):
    """bad_line_end is a human readable string."""
    e = InvalidLineEnd(bad_line_end=bad_line_end, context=context,
                       context2=self._context, type=TYPE_WARNING)
    self._Report(e)

  def TooFastTravel(self, trip_id, prev_stop, next_stop, dist, time, speed,
                    type=TYPE_ERROR):
    e = TooFastTravel(trip_id=trip_id, prev_stop=prev_stop,
                      next_stop=next_stop, time=time, dist=dist, speed=speed,
                      context=None, context2=self._context, type=type)
    self._Report(e)

  def StopWithMultipleRouteTypes(self, stop_name, stop_id, route_id1, route_id2,
                                 context=None):
    e = StopWithMultipleRouteTypes(stop_name=stop_name, stop_id=stop_id,
                                   route_id1=route_id1, route_id2=route_id2,
                                   context=context, context2=self._context,
                                   type=TYPE_WARNING)
    self._Report(e)

  def DuplicateTrip(self, trip_id1, route_id1, trip_id2, route_id2,
                    context=None):
    e = DuplicateTrip(trip_id1=trip_id1, route_id1=route_id1, trip_id2=trip_id2,
                      route_id2=route_id2, context=context,
                      context2=self._context, type=TYPE_WARNING)
    self._Report(e)

  def OtherProblem(self, description, context=None, type=TYPE_ERROR):
    e = OtherProblem(description=description,
                    context=context, context2=self._context, type=type)
    self._Report(e)

  def TooManyDaysWithoutService(self,
                                first_day_without_service,
                                last_day_without_service,
                                consecutive_days_without_service,
                                context=None, 
                                type=TYPE_WARNING):
    e = TooManyDaysWithoutService(
        first_day_without_service=first_day_without_service,
        last_day_without_service=last_day_without_service,
        consecutive_days_without_service=consecutive_days_without_service,
        context=context,
        context2=self._context,
        type=type)
    self._Report(e)

class ProblemReporter(ProblemReporterBase):
  """This is a basic problem reporter that just prints to console."""
  def _Report(self, e):
    context = e.FormatContext()
    if context:
      print context
    print EncodeUnicode(self._LineWrap(e.FormatProblem(), 78))

  @staticmethod
  def _LineWrap(text, width):
    """
    A word-wrap function that preserves existing line breaks
    and most spaces in the text. Expects that existing line
    breaks are posix newlines (\n).

    Taken from:
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/148061
    """
    return reduce(lambda line, word, width=width: '%s%s%s' %
                  (line,
                   ' \n'[(len(line) - line.rfind('\n') - 1 +
                         len(word.split('\n', 1)[0]) >= width)],
                   word),
                  text.split(' ')
                 )


class ExceptionWithContext(Exception):
  def __init__(self, context=None, context2=None, **kwargs):
    """Initialize an exception object, saving all keyword arguments in self.
    context and context2, if present, must be a tuple of (file_name, row_num,
    row, headers). context2 comes from ProblemReporter.SetFileContext. context
    was passed in with the keyword arguments. context2 is ignored if context
    is present."""
    Exception.__init__(self)

    if context:
      self.__dict__.update(self.ContextTupleToDict(context))
    elif context2:
      self.__dict__.update(self.ContextTupleToDict(context2))
    self.__dict__.update(kwargs)

    if ('type' in kwargs) and (kwargs['type'] == TYPE_WARNING):
      self._type = TYPE_WARNING
    else:
      self._type = TYPE_ERROR

  def GetType(self):
    return self._type

  def IsError(self):
    return self._type == TYPE_ERROR

  def IsWarning(self):
    return self._type == TYPE_WARNING

  CONTEXT_PARTS = ['file_name', 'row_num', 'row', 'headers']
  @staticmethod
  def ContextTupleToDict(context):
    """Convert a tuple representing a context into a dict of (key, value) pairs"""
    d = {}
    if not context:
      return d
    for k, v in zip(ExceptionWithContext.CONTEXT_PARTS, context):
      if v != '' and v != None:  # Don't ignore int(0), a valid row_num
        d[k] = v
    return d

  def __str__(self):
    return self.FormatProblem()

  def GetDictToFormat(self):
    """Return a copy of self as a dict, suitable for passing to FormatProblem"""
    d = {}
    for k, v in self.__dict__.items():
      # TODO: Better handling of unicode/utf-8 within Schedule objects.
      # Concatinating a unicode and utf-8 str object causes an exception such
      # as "UnicodeDecodeError: 'ascii' codec can't decode byte ..." as python
      # tries to convert the str to a unicode. To avoid that happening within
      # the problem reporter convert all unicode attributes to utf-8.
      # Currently valid utf-8 fields are converted to unicode in _ReadCsvDict.
      # Perhaps all fields should be left as utf-8.
      d[k] = EncodeUnicode(v)
    return d

  def FormatProblem(self, d=None):
    """Return a text string describing the problem.

    Args:
      d: map returned by GetDictToFormat with  with formatting added
    """
    if not d:
      d = self.GetDictToFormat()

    output_error_text = self.__class__.ERROR_TEXT % d
    if ('reason' in d) and d['reason']:
      return '%s\n%s' % (output_error_text, d['reason'])
    else:
      return output_error_text

  def FormatContext(self):
    """Return a text string describing the context"""
    text = ''
    if hasattr(self, 'feed_name'):
      text += "In feed '%s': " % self.feed_name
    if hasattr(self, 'file_name'):
      text += self.file_name
    if hasattr(self, 'row_num'):
      text += ":%i" % self.row_num
    if hasattr(self, 'column_name'):
      text += " column %s" % self.column_name
    return text

  def __cmp__(self, y):
    """Return an int <0/0/>0 when self is more/same/less significant than y.

    Subclasses should define this if exceptions should be listed in something
    other than the order they are reported.

    Args:
      y: object to compare to self

    Returns:
      An int which is negative if self is more significant than y, 0 if they
      are similar significance and positive if self is less significant than
      y. Returning a float won't work.

    Raises:
      TypeError by default, meaning objects of the type can not be compared.
    """
    raise TypeError("__cmp__ not defined")


class MissingFile(ExceptionWithContext):
  ERROR_TEXT = "File %(file_name)s is not found"

class EmptyFile(ExceptionWithContext):
  ERROR_TEXT = "File %(file_name)s is empty"

class UnknownFile(ExceptionWithContext):
  ERROR_TEXT = 'The file named %(file_name)s was not expected.\n' \
               'This may be a misspelled file name or the file may be ' \
               'included in a subdirectory. Please check spellings and ' \
               'make sure that there are no subdirectories within the feed'

class FeedNotFound(ExceptionWithContext):
  ERROR_TEXT = 'Couldn\'t find a feed named %(feed_name)s'

class UnknownFormat(ExceptionWithContext):
  ERROR_TEXT = 'The feed named %(feed_name)s had an unknown format:\n' \
               'feeds should be either .zip files or directories.'

class FileFormat(ExceptionWithContext):
  ERROR_TEXT = 'Files must be encoded in utf-8 and may not contain ' \
               'any null bytes (0x00). %(file_name)s %(problem)s.'

class MissingColumn(ExceptionWithContext):
  ERROR_TEXT = 'Missing column %(column_name)s in file %(file_name)s'

class UnrecognizedColumn(ExceptionWithContext):
  ERROR_TEXT = 'Unrecognized column %(column_name)s in file %(file_name)s. ' \
               'This might be a misspelled column name (capitalization ' \
               'matters!). Or it could be extra information (such as a ' \
               'proposed feed extension) that the validator doesn\'t know ' \
               'about yet. Extra information is fine; this warning is here ' \
               'to catch misspelled optional column names.'

class CsvSyntax(ExceptionWithContext):
  ERROR_TEXT = '%(description)s'

class DuplicateColumn(ExceptionWithContext):
  ERROR_TEXT = 'Column %(header)s appears %(count)i times in file %(file_name)s'

class MissingValue(ExceptionWithContext):
  ERROR_TEXT = 'Missing value for column %(column_name)s'

class InvalidValue(ExceptionWithContext):
  ERROR_TEXT = 'Invalid value %(value)s in field %(column_name)s'

class DuplicateID(ExceptionWithContext):
  ERROR_TEXT = 'Duplicate ID %(value)s in column %(column_name)s'

class UnusedStop(ExceptionWithContext):
  ERROR_TEXT = "%(stop_name)s (ID %(stop_id)s) isn't used in any trips"

class UsedStation(ExceptionWithContext):
  ERROR_TEXT = "%(stop_name)s (ID %(stop_id)s) has location_type=1 " \
               "(station) so it should not appear in stop_times"

class StopTooFarFromParentStation(ExceptionWithContext):
  ERROR_TEXT = (
      "%(stop_name)s (ID %(stop_id)s) is too far from its parent station "
      "%(parent_stop_name)s (ID %(parent_stop_id)s) : %(distance).2f meters.")
  def __cmp__(self, y):
    # Sort in decreasing order because more distance is more significant.
    return cmp(y.distance, self.distance)


class StopsTooClose(ExceptionWithContext):
  ERROR_TEXT = (
      "The stops \"%(stop_name_a)s\" (ID %(stop_id_a)s) and \"%(stop_name_b)s\""
      " (ID %(stop_id_b)s) are %(distance)0.2fm apart and probably represent "
      "the same location.")
  def __cmp__(self, y):
    # Sort in increasing order because less distance is more significant.
    return cmp(self.distance, y.distance)

class StationsTooClose(ExceptionWithContext):
  ERROR_TEXT = (
      "The stations \"%(stop_name_a)s\" (ID %(stop_id_a)s) and "
      "\"%(stop_name_b)s\" (ID %(stop_id_b)s) are %(distance)0.2fm apart and "
      "probably represent the same location.")
  def __cmp__(self, y):
    # Sort in increasing order because less distance is more significant.
    return cmp(self.distance, y.distance)

class DifferentStationTooClose(ExceptionWithContext):
  ERROR_TEXT = (
      "The parent_station of stop \"%(stop_name)s\" (ID %(stop_id)s) is not "
      "station \"%(station_stop_name)s\" (ID %(station_stop_id)s) but they are "
      "only %(distance)0.2fm apart.")
  def __cmp__(self, y):
    # Sort in increasing order because less distance is more significant.
    return cmp(self.distance, y.distance)

class StopTooFarFromShapeWithDistTraveled(ExceptionWithContext):
  ERROR_TEXT = (
      "For trip %(trip_id)s the stop \"%(stop_name)s\" (ID %(stop_id)s) is "
      "%(distance).0f meters away from the corresponding point "
      "(shape_dist_traveled: %(shape_dist_traveled)f) on shape %(shape_id)s. "
      "It should be closer than %(max_distance).0f meters.")
  def __cmp__(self, y):
    # Sort in decreasing order because more distance is more significant.
    return cmp(y.distance, self.distance)


class TooManyDaysWithoutService(ExceptionWithContext):
  ERROR_TEXT = "There are %(consecutive_days_without_service)i consecutive"\
               " days, from %(first_day_without_service)s to" \
               " %(last_day_without_service)s, without any scheduled service." \
               " Please ensure this is intentional."


class ExpirationDate(ExceptionWithContext):
  def FormatProblem(self, d=None):
    if not d:
      d = self.GetDictToFormat()
    expiration = d['expiration']
    formatted_date = time.strftime("%B %d, %Y",
                                   time.localtime(expiration))
    if (expiration < time.mktime(time.localtime())):
      return "This feed expired on %s" % formatted_date
    else:
      return "This feed will soon expire, on %s" % formatted_date

class FutureService(ExceptionWithContext):
  def FormatProblem(self, d=None):
    if not d:
      d = self.GetDictToFormat()
    formatted_date = time.strftime("%B %d, %Y", time.localtime(d['start_date']))
    return ("The earliest service date in this feed is in the future, on %s. "
            "Published feeds must always include the current date." %
            formatted_date)


class InvalidLineEnd(ExceptionWithContext):
  ERROR_TEXT = "Each line must end with CR LF or LF except for the last line " \
               "of the file. This line ends with \"%(bad_line_end)s\"."

class StopWithMultipleRouteTypes(ExceptionWithContext):
  ERROR_TEXT = "Stop %(stop_name)s (ID=%(stop_id)s) belongs to both " \
               "subway (ID=%(route_id1)s) and bus line (ID=%(route_id2)s)."

class TooFastTravel(ExceptionWithContext):
  def FormatProblem(self, d=None):
    if not d:
      d = self.GetDictToFormat()
    if not d['speed']:
      return "High speed travel detected in trip %(trip_id)s: %(prev_stop)s" \
                " to %(next_stop)s. %(dist).0f meters in %(time)d seconds." % d
    else:
      return "High speed travel detected in trip %(trip_id)s: %(prev_stop)s" \
             " to %(next_stop)s. %(dist).0f meters in %(time)d seconds." \
             " (%(speed).0f km/h)." % d
  def __cmp__(self, y):
    # Sort in decreasing order because more distance is more significant. We
    # can't sort by speed because not all TooFastTravel objects have a speed.
    return cmp(y.dist, self.dist)

class DuplicateTrip(ExceptionWithContext):
  ERROR_TEXT = "Trip %(trip_id1)s of route %(route_id1)s might be duplicated " \
               "with trip %(trip_id2)s of route %(route_id2)s. They go " \
               "through the same stops with same service."

class OtherProblem(ExceptionWithContext):
  ERROR_TEXT = '%(description)s'


class ExceptionProblemReporter(ProblemReporter):
  def __init__(self, raise_warnings=False):
    ProblemReporterBase.__init__(self)
    self.raise_warnings = raise_warnings

  def _Report(self, e):
    if self.raise_warnings or e.IsError():
      raise e
    else:
      ProblemReporter._Report(self, e)


default_problem_reporter = ExceptionProblemReporter()

# Add a default handler to send log messages to console
console = logging.StreamHandler()
console.setLevel(logging.WARNING)
log = logging.getLogger("schedule_builder")
log.addHandler(console)


class Error(Exception):
  pass


def IsValidURL(url):
  """Checks the validity of a URL value."""
  # TODO: Add more thorough checking of URL
  return url.startswith(u'http://') or url.startswith(u'https://')


def IsValidColor(color):
  """Checks the validity of a hex color value."""
  return not re.match('^[0-9a-fA-F]{6}$', color) == None


def ColorLuminance(color):
  """Compute the brightness of an sRGB color using the formula from
  http://www.w3.org/TR/2000/WD-AERT-20000426#color-contrast.

  Args:
    color: a string of six hex digits in the format verified by IsValidColor().

  Returns:
    A floating-point number between 0.0 (black) and 255.0 (white). """
  r = int(color[0:2], 16)
  g = int(color[2:4], 16)
  b = int(color[4:6], 16)
  return (299*r + 587*g + 114*b) / 1000.0


def IsEmpty(value):
  return value is None or (isinstance(value, basestring) and not value.strip())


def FindUniqueId(dic):
  """Return a string not used as a key in the dictionary dic"""
  name = str(len(dic))
  while name in dic:
    name = str(random.randint(1, 999999999))
  return name


def TimeToSecondsSinceMidnight(time_string):
  """Convert HHH:MM:SS into seconds since midnight.

  For example "01:02:03" returns 3723. The leading zero of the hours may be
  omitted. HH may be more than 23 if the time is on the following day."""
  m = re.match(r'(\d{1,3}):([0-5]\d):([0-5]\d)$', time_string)
  # ignored: matching for leap seconds
  if not m:
    raise Error, 'Bad HH:MM:SS "%s"' % time_string
  return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def FormatSecondsSinceMidnight(s):
  """Formats an int number of seconds past midnight into a string
  as "HH:MM:SS"."""
  return "%02d:%02d:%02d" % (s / 3600, (s / 60) % 60, s % 60)


def DateStringToDateObject(date_string):
  """Return a date object for a string "YYYYMMDD"."""
  # If this becomes a bottleneck date objects could be cached
  return datetime.date(int(date_string[0:4]), int(date_string[4:6]),
                       int(date_string[6:8]))


def FloatStringToFloat(float_string):
  """Convert a float as a string to a float or raise an exception"""
  # Will raise TypeError unless a string
  if not re.match(r"^[+-]?\d+(\.\d+)?$", float_string):
    raise ValueError()
  return float(float_string)


def NonNegIntStringToInt(int_string):
  """Convert an non-negative integer string to an int or raise an exception"""
  # Will raise TypeError unless a string
  if not re.match(r"^(?:0|[1-9]\d*)$", int_string):
    raise ValueError()
  return int(int_string)


EARTH_RADIUS = 6378135          # in meters
def ApproximateDistance(degree_lat1, degree_lng1, degree_lat2, degree_lng2):
  """Compute approximate distance between two points in meters. Assumes the
  Earth is a sphere."""
  # TODO: change to ellipsoid approximation, such as
  # http://www.codeguru.com/Cpp/Cpp/algorithms/article.php/c5115/
  lat1 = math.radians(degree_lat1)
  lng1 = math.radians(degree_lng1)
  lat2 = math.radians(degree_lat2)
  lng2 = math.radians(degree_lng2)
  dlat = math.sin(0.5 * (lat2 - lat1))
  dlng = math.sin(0.5 * (lng2 - lng1))
  x = dlat * dlat + dlng * dlng * math.cos(lat1) * math.cos(lat2)
  return EARTH_RADIUS * (2 * math.atan2(math.sqrt(x),
      math.sqrt(max(0.0, 1.0 - x))))


def ApproximateDistanceBetweenStops(stop1, stop2):
  """Compute approximate distance between two stops in meters. Assumes the
  Earth is a sphere."""
  return ApproximateDistance(stop1.stop_lat, stop1.stop_lon,
                             stop2.stop_lat, stop2.stop_lon)


class GenericGTFSObject(object):
  """Object with arbitrary attributes which may be added to a schedule.

  This class should be used as the base class for GTFS objects which may
  be stored in a Schedule. It defines some methods for reading and writing
  attributes. If self._schedule is None than the object is not in a Schedule.

  Subclasses must:
  * define an __init__ method which sets the _schedule member to None or a
    weakref to a Schedule
  * Set the _TABLE_NAME class variable to a name such as 'stops', 'agency', ...
  * define methods to validate objects of that type
  """
  def __getitem__(self, name):
    """Return a unicode or str representation of name or "" if not set."""
    if name in self.__dict__ and self.__dict__[name] is not None:
      return "%s" % self.__dict__[name]
    else:
      return ""

  def __getattr__(self, name):
    """Return None or the default value if name is a known attribute.

    This method is only called when name is not found in __dict__.
    """
    if name in self.__class__._FIELD_NAMES:
      return None
    else:
      raise AttributeError(name)

  def iteritems(self):
    """Return a iterable for (name, value) pairs of public attributes."""
    for name, value in self.__dict__.iteritems():
      if (not name) or name[0] == "_":
        continue
      yield name, value

  def __setattr__(self, name, value):
    """Set an attribute, adding name to the list of columns as needed."""
    object.__setattr__(self, name, value)
    if name[0] != '_' and self._schedule:
      self._schedule.AddTableColumn(self.__class__._TABLE_NAME, name)

  def __eq__(self, other):
    """Return true iff self and other are equivalent"""
    if not other:
      return False

    if id(self) == id(other):
      return True

    for k in self.keys().union(other.keys()):
      # use __getitem__ which returns "" for missing columns values
      if self[k] != other[k]:
        return False
    return True

  def __ne__(self, other):
    return not self.__eq__(other)

  def __repr__(self):
    return "<%s %s>" % (self.__class__.__name__, sorted(self.iteritems()))

  def keys(self):
    """Return iterable of columns used by this object."""
    columns = set()
    for name in vars(self):
      if (not name) or name[0] == "_":
        continue
      columns.add(name)
    return columns

  def _ColumnNames(self):
    return self.keys()


class Stop(GenericGTFSObject):
  """Represents a single stop. A stop must have a latitude, longitude and name.

  Callers may assign arbitrary values to instance attributes.
  Stop.ParseAttributes validates attributes according to GTFS and converts some
  into native types. ParseAttributes may delete invalid attributes.
  Accessing an attribute that is a column in GTFS will return None if this
  object does not have a value or it is ''.
  A Stop object acts like a dict with string values.

  Attributes:
    stop_lat: a float representing the latitude of the stop
    stop_lon: a float representing the longitude of the stop
    All other attributes are strings.
  """
  _REQUIRED_FIELD_NAMES = ['stop_id', 'stop_name', 'stop_lat', 'stop_lon']
  _FIELD_NAMES = _REQUIRED_FIELD_NAMES + \
                 ['stop_desc', 'zone_id', 'stop_url', 'stop_code',
                  'location_type', 'parent_station']
  _TABLE_NAME = 'stops'

  def __init__(self, lat=None, lng=None, name=None, stop_id=None,
               field_dict=None, stop_code=None):
    """Initialize a new Stop object.

    Args:
      field_dict: A dictionary mapping attribute name to unicode string
      lat: a float, ignored when field_dict is present
      lng: a float, ignored when field_dict is present
      name: a string, ignored when field_dict is present
      stop_id: a string, ignored when field_dict is present
      stop_code: a string, ignored when field_dict is present
    """
    self._schedule = None
    if field_dict:
      if isinstance(field_dict, Stop):
        # Special case so that we don't need to re-parse the attributes to
        # native types iteritems returns all attributes that don't start with _
        for k, v in field_dict.iteritems():
          self.__dict__[k] = v
      else:
        self.__dict__.update(field_dict)
    else:
      if lat is not None:
        self.stop_lat = lat
      if lng is not None:
        self.stop_lon = lng
      if name is not None:
        self.stop_name = name
      if stop_id is not None:
        self.stop_id = stop_id
      if stop_code is not None:
        self.stop_code = stop_code

  def GetTrips(self, schedule=None):
    """Return iterable containing trips that visit this stop."""
    return [trip for trip, ss in self._GetTripSequence(schedule)]

  def _GetTripSequence(self, schedule=None):
    """Return a list of (trip, stop_sequence) for all trips visiting this stop.

    A trip may be in the list multiple times with different index.
    stop_sequence is an integer.

    Args:
      schedule: Deprecated, do not use.
    """
    if schedule is None:
      schedule = getattr(self, "_schedule", None)
    if schedule is None:
      warnings.warn("No longer supported. _schedule attribute is  used to get "
                    "stop_times table", DeprecationWarning)
    cursor = schedule._connection.cursor()
    cursor.execute("SELECT trip_id,stop_sequence FROM stop_times "
                   "WHERE stop_id=?",
                   (self.stop_id, ))
    return [(schedule.GetTrip(row[0]), row[1]) for row in cursor]

  def _GetTripIndex(self, schedule=None):
    """Return a list of (trip, index).

    trip: a Trip object
    index: an offset in trip.GetStopTimes()
    """
    trip_index = []
    for trip, sequence in self._GetTripSequence(schedule):
      for index, st in enumerate(trip.GetStopTimes()):
        if st.stop_sequence == sequence:
          trip_index.append((trip, index))
          break
      else:
        raise RuntimeError("stop_sequence %d not found in trip_id %s" %
                           sequence, trip.trip_id)
    return trip_index

  def GetStopTimeTrips(self, schedule=None):
    """Return a list of (time, (trip, index), is_timepoint).

    time: an integer. It might be interpolated.
    trip: a Trip object.
    index: the offset of this stop in trip.GetStopTimes(), which may be
      different from the stop_sequence.
    is_timepoint: a bool
    """
    time_trips = []
    for trip, index in self._GetTripIndex(schedule):
      secs, stoptime, is_timepoint = trip.GetTimeInterpolatedStops()[index]
      time_trips.append((secs, (trip, index), is_timepoint))
    return time_trips

  def ParseAttributes(self, problems):
    """Parse all attributes, calling problems as needed."""
    # Need to use items() instead of iteritems() because _CheckAndSetAttr may
    # modify self.__dict__
    for name, value in vars(self).items():
      if name[0] == "_":
        continue
      self._CheckAndSetAttr(name, value, problems)

  def _CheckAndSetAttr(self, name, value, problems):
    """If value is valid for attribute name store it.

    If value is not valid call problems. Return a new value of the correct type
    or None if value couldn't be converted.
    """
    if name == 'stop_lat':
      try:
        if isinstance(value, (float, int)):
          self.stop_lat = value
        else:
          self.stop_lat = FloatStringToFloat(value)
      except (ValueError, TypeError):
        problems.InvalidValue('stop_lat', value)
        del self.stop_lat
      else:
        if self.stop_lat > 90 or self.stop_lat < -90:
          problems.InvalidValue('stop_lat', value)
    elif name == 'stop_lon':
      try:
        if isinstance(value, (float, int)):
          self.stop_lon = value
        else:
          self.stop_lon = FloatStringToFloat(value)
      except (ValueError, TypeError):
        problems.InvalidValue('stop_lon', value)
        del self.stop_lon
      else:
        if self.stop_lon > 180 or self.stop_lon < -180:
          problems.InvalidValue('stop_lon', value)
    elif name == 'stop_url':
      if value and not IsValidURL(value):
        problems.InvalidValue('stop_url', value)
        del self.stop_url
    elif name == 'location_type':
      if value == '':
        self.location_type = 0
      else:
        try:
          self.location_type = int(value)
        except (ValueError, TypeError):
          problems.InvalidValue('location_type', value)
          del self.location_type
        else:
          if self.location_type not in (0, 1):
            problems.InvalidValue('location_type', value, type=TYPE_WARNING)

  def __getattr__(self, name):
    """Return None or the default value if name is a known attribute.

    This method is only called when name is not found in __dict__.
    """
    if name == "location_type":
      return 0
    elif name == "trip_index":
      return self._GetTripIndex()
    elif name in Stop._FIELD_NAMES:
      return None
    else:
      raise AttributeError(name)

  def Validate(self, problems=default_problem_reporter):
    # First check that all required fields are present because ParseAttributes
    # may remove invalid attributes.
    for required in Stop._REQUIRED_FIELD_NAMES:
      if IsEmpty(getattr(self, required, None)):
        # TODO: For now I'm keeping the API stable but it would be cleaner to
        # treat whitespace stop_id as invalid, instead of missing
        problems.MissingValue(required)

    # Check individual values and convert to native types
    self.ParseAttributes(problems)

    # Check that this object is consistent with itself
    if (self.stop_lat is not None and self.stop_lon is not None and
        abs(self.stop_lat) < 1.0) and (abs(self.stop_lon) < 1.0):
      problems.InvalidValue('stop_lat', self.stop_lat,
                            'Stop location too close to 0, 0',
                            type=TYPE_WARNING)
    if (self.stop_desc is not None and self.stop_name is not None and
        self.stop_desc and self.stop_name and
        not IsEmpty(self.stop_desc) and
        self.stop_name.strip().lower() == self.stop_desc.strip().lower()):
      problems.InvalidValue('stop_desc', self.stop_desc,
                            'stop_desc should not be the same as stop_name')

    if self.parent_station and self.location_type == 1:
      problems.InvalidValue('parent_station', self.parent_station,
                            'Stop row with location_type=1 (a station) must '
                            'not have a parent_station')


class Route(GenericGTFSObject):
  """Represents a single route."""

  _REQUIRED_FIELD_NAMES = [
    'route_id', 'route_short_name', 'route_long_name', 'route_type'
    ]
  _FIELD_NAMES = _REQUIRED_FIELD_NAMES + [
    'agency_id', 'route_desc', 'route_url', 'route_color', 'route_text_color'
    ]
  _ROUTE_TYPES = {
    0: {'name':'Tram', 'max_speed':100},
    1: {'name':'Subway', 'max_speed':150},
    2: {'name':'Rail', 'max_speed':300},
    3: {'name':'Bus', 'max_speed':100},
    4: {'name':'Ferry', 'max_speed':80},
    5: {'name':'Cable Car', 'max_speed':50},
    6: {'name':'Gondola', 'max_speed':50},
    7: {'name':'Funicular', 'max_speed':50},
    }
  # Create a reverse lookup dict of route type names to route types.
  _ROUTE_TYPE_IDS = set(_ROUTE_TYPES.keys())
  _ROUTE_TYPE_NAMES = dict((v['name'], k) for k, v in _ROUTE_TYPES.items())
  _TABLE_NAME = 'routes'

  def __init__(self, short_name=None, long_name=None, route_type=None,
               route_id=None, agency_id=None, field_dict=None):
    self._schedule = None
    self._trips = []

    if not field_dict:
      field_dict = {}
      if short_name is not None:
        field_dict['route_short_name'] = short_name
      if long_name is not None:
        field_dict['route_long_name'] = long_name
      if route_type is not None:
        if route_type in Route._ROUTE_TYPE_NAMES:
          self.route_type = Route._ROUTE_TYPE_NAMES[route_type]
        else:
          field_dict['route_type'] = route_type
      if route_id is not None:
        field_dict['route_id'] = route_id
      if agency_id is not None:
        field_dict['agency_id'] = agency_id
    self.__dict__.update(field_dict)

  def AddTrip(self, schedule, headsign, service_period=None, trip_id=None):
    """ Adds a trip to this route.

    Args:
      headsign: headsign of the trip as a string

    Returns:
      a new Trip object
    """
    if trip_id is None:
      trip_id = unicode(len(schedule.trips))
    if service_period is None:
      service_period = schedule.GetDefaultServicePeriod()
    trip = Trip(route=self, headsign=headsign, service_period=service_period,
                trip_id=trip_id)
    schedule.AddTripObject(trip)
    return trip

  def _AddTripObject(self, trip):
    # Only class Schedule may call this. Users of the API should call
    # Route.AddTrip or schedule.AddTripObject.
    self._trips.append(trip)

  def __getattr__(self, name):
    """Return None or the default value if name is a known attribute.

    This method overrides GenericGTFSObject.__getattr__ to provide backwards
    compatible access to trips.
    """
    if name == 'trips':
      return self._trips
    else:
      return GenericGTFSObject.__getattr__(self, name)

  def GetPatternIdTripDict(self):
    """Return a dictionary that maps pattern_id to a list of Trip objects."""
    d = {}
    for t in self._trips:
      d.setdefault(t.pattern_id, []).append(t)
    return d

  def Validate(self, problems=default_problem_reporter):
    if IsEmpty(self.route_id):
      problems.MissingValue('route_id')
    if IsEmpty(self.route_type):
      problems.MissingValue('route_type')

    if IsEmpty(self.route_short_name) and IsEmpty(self.route_long_name):
      problems.InvalidValue('route_short_name',
                            self.route_short_name,
                            'Both route_short_name and '
                            'route_long name are blank.')

    if self.route_short_name and len(self.route_short_name) > 6:
      problems.InvalidValue('route_short_name',
                            self.route_short_name,
                            'This route_short_name is relatively long, which '
                            'probably means that it contains a place name.  '
                            'You should only use this field to hold a short '
                            'code that riders use to identify a route.  '
                            'If this route doesn\'t have such a code, it\'s '
                            'OK to leave this field empty.', type=TYPE_WARNING)

    if self.route_short_name and self.route_long_name:
      short_name = self.route_short_name.strip().lower()
      long_name = self.route_long_name.strip().lower()
      if (long_name.startswith(short_name + ' ') or
          long_name.startswith(short_name + '(') or
          long_name.startswith(short_name + '-')):
        problems.InvalidValue('route_long_name',
                              self.route_long_name,
                              'route_long_name shouldn\'t contain '
                              'the route_short_name value, as both '
                              'fields are often displayed '
                              'side-by-side.', type=TYPE_WARNING)
      if long_name == short_name:
        problems.InvalidValue('route_long_name',
                              self.route_long_name,
                              'route_long_name shouldn\'t be the same '
                              'the route_short_name value, as both '
                              'fields are often displayed '
                              'side-by-side.  It\'s OK to omit either the '
                              'short or long name (but not both).',
                              type=TYPE_WARNING)
    if (self.route_desc and
        ((self.route_desc == self.route_short_name) or
         (self.route_desc == self.route_long_name))):
      problems.InvalidValue('route_desc',
                            self.route_desc,
                            'route_desc shouldn\'t be the same as '
                            'route_short_name or route_long_name')

    if self.route_type is not None:
      try:
        if not isinstance(self.route_type, int):
          self.route_type = NonNegIntStringToInt(self.route_type)
      except (TypeError, ValueError):
        problems.InvalidValue('route_type', self.route_type)
      else:
        if self.route_type not in Route._ROUTE_TYPE_IDS:
          problems.InvalidValue('route_type',
                                self.route_type,
                                type=TYPE_WARNING)

    if self.route_url and not IsValidURL(self.route_url):
      problems.InvalidValue('route_url', self.route_url)

    txt_lum = ColorLuminance('000000')  # black (default)
    bg_lum = ColorLuminance('ffffff')   # white (default)
    if self.route_color:
      if IsValidColor(self.route_color):
        bg_lum  = ColorLuminance(self.route_color)
      else:
        problems.InvalidValue('route_color', self.route_color,
                              'route_color should be a valid color description '
                              'which consists of 6 hexadecimal characters '
                              'representing the RGB values. Example: 44AA06')
    if self.route_text_color:
      if IsValidColor(self.route_text_color):
        txt_lum = ColorLuminance(self.route_text_color)
      else:
        problems.InvalidValue('route_text_color', self.route_text_color,
                              'route_text_color should be a valid color '
                              'description, which consists of 6 hexadecimal '
                              'characters representing the RGB values. '
                              'Example: 44AA06')
    if abs(txt_lum - bg_lum) < 510/7.:
      # http://www.w3.org/TR/2000/WD-AERT-20000426#color-contrast recommends
      # a threshold of 125, but that is for normal text and too harsh for
      # big colored logos like line names, so we keep the original threshold
      # from r541 (but note that weight has shifted between RGB components).
      problems.InvalidValue('route_color', self.route_color,
                            'The route_text_color and route_color should '
                            'be set to contrasting colors, as they are used '
                            'as the text and background color (respectively) '
                            'for displaying route names.  When left blank, '
                            'route_text_color defaults to 000000 (black) and '
                            'route_color defaults to FFFFFF (white).  A common '
                            'source of issues here is setting route_color to '
                            'a dark color, while leaving route_text_color set '
                            'to black.  In this case, route_text_color should '
                            'be set to a lighter color like FFFFFF to ensure '
                            'a legible contrast between the two.',
                            type=TYPE_WARNING)


def SortListOfTripByTime(trips):
  trips.sort(key=Trip.GetStartTime)


class StopTime(object):
  """
  Represents a single stop of a trip. StopTime contains most of the columns
  from the stop_times.txt file. It does not contain trip_id, which is implied
  by the Trip used to access it.

  See the Google Transit Feed Specification for the semantic details.

  stop: A Stop object
  arrival_time: str in the form HH:MM:SS; readonly after __init__
  departure_time: str in the form HH:MM:SS; readonly after __init__
  arrival_secs: int number of seconds since midnight
  departure_secs: int number of seconds since midnight
  stop_headsign: str
  pickup_type: int
  drop_off_type: int
  shape_dist_traveled: float
  stop_id: str; readonly
  stop_time: The only time given for this stop.  If present, it is used
             for both arrival and departure time.
  stop_sequence: int
  """
  _REQUIRED_FIELD_NAMES = ['trip_id', 'arrival_time', 'departure_time',
                           'stop_id', 'stop_sequence']
  _OPTIONAL_FIELD_NAMES = ['stop_headsign', 'pickup_type',
                           'drop_off_type', 'shape_dist_traveled']
  _FIELD_NAMES = _REQUIRED_FIELD_NAMES + _OPTIONAL_FIELD_NAMES
  _SQL_FIELD_NAMES = ['trip_id', 'arrival_secs', 'departure_secs',
                      'stop_id', 'stop_sequence', 'stop_headsign',
                      'pickup_type', 'drop_off_type', 'shape_dist_traveled']

  __slots__ = ('arrival_secs', 'departure_secs', 'stop_headsign', 'stop',
               'stop_headsign', 'pickup_type', 'drop_off_type',
               'shape_dist_traveled', 'stop_sequence')
  def __init__(self, problems, stop,
               arrival_time=None, departure_time=None,
               stop_headsign=None, pickup_type=None, drop_off_type=None,
               shape_dist_traveled=None, arrival_secs=None,
               departure_secs=None, stop_time=None, stop_sequence=None):
    if stop_time != None:
      arrival_time = departure_time = stop_time

    if arrival_secs != None:
      self.arrival_secs = arrival_secs
    elif arrival_time in (None, ""):
      self.arrival_secs = None  # Untimed
      arrival_time = None
    else:
      try:
        self.arrival_secs = TimeToSecondsSinceMidnight(arrival_time)
      except Error:
        problems.InvalidValue('arrival_time', arrival_time)
        self.arrival_secs = None

    if departure_secs != None:
      self.departure_secs = departure_secs
    elif departure_time in (None, ""):
      self.departure_secs = None
      departure_time = None
    else:
      try:
        self.departure_secs = TimeToSecondsSinceMidnight(departure_time)
      except Error:
        problems.InvalidValue('departure_time', departure_time)
        self.departure_secs = None

    if not isinstance(stop, Stop):
      # Not quite correct, but better than letting the problem propagate
      problems.InvalidValue('stop', stop)
    self.stop = stop
    self.stop_headsign = stop_headsign

    if pickup_type in (None, ""):
      self.pickup_type = None
    else:
      try:
        pickup_type = int(pickup_type)
      except ValueError:
        problems.InvalidValue('pickup_type', pickup_type)
      else:
        if pickup_type < 0 or pickup_type > 3:
          problems.InvalidValue('pickup_type', pickup_type)
      self.pickup_type = pickup_type

    if drop_off_type in (None, ""):
      self.drop_off_type = None
    else:
      try:
        drop_off_type = int(drop_off_type)
      except ValueError:
        problems.InvalidValue('drop_off_type', drop_off_type)
      else:
        if drop_off_type < 0 or drop_off_type > 3:
          problems.InvalidValue('drop_off_type', drop_off_type)
      self.drop_off_type = drop_off_type

    if (self.pickup_type == 1 and self.drop_off_type == 1 and
        self.arrival_secs == None and self.departure_secs == None):
      problems.OtherProblem('This stop time has a pickup_type and '
                            'drop_off_type of 1, indicating that riders '
                            'can\'t get on or off here.  Since it doesn\'t '
                            'define a timepoint either, this entry serves no '
                            'purpose and should be excluded from the trip.',
                            type=TYPE_WARNING)

    if ((self.arrival_secs != None) and (self.departure_secs != None) and
        (self.departure_secs < self.arrival_secs)):
      problems.InvalidValue('departure_time', departure_time,
                            'The departure time at this stop (%s) is before '
                            'the arrival time (%s).  This is often caused by '
                            'problems in the feed exporter\'s time conversion')

    # If the caller passed a valid arrival time but didn't attempt to pass a
    # departure time complain
    if (self.arrival_secs != None and
        self.departure_secs == None and departure_time == None):
      # self.departure_secs might be None because departure_time was invalid,
      # so we need to check both
      problems.MissingValue('departure_time',
                            'arrival_time and departure_time should either '
                            'both be provided or both be left blank.  '
                            'It\'s OK to set them both to the same value.')
    # If the caller passed a valid departure time but didn't attempt to pass a
    # arrival time complain
    if (self.departure_secs != None and
        self.arrival_secs == None and arrival_time == None):
      problems.MissingValue('arrival_time',
                            'arrival_time and departure_time should either '
                            'both be provided or both be left blank.  '
                            'It\'s OK to set them both to the same value.')

    if shape_dist_traveled in (None, ""):
      self.shape_dist_traveled = None
    else:
      try:
        self.shape_dist_traveled = float(shape_dist_traveled)
      except ValueError:
        problems.InvalidValue('shape_dist_traveled', shape_dist_traveled)

    if stop_sequence is not None:
      self.stop_sequence = stop_sequence

  def GetFieldValuesTuple(self, trip_id):
    """Return a tuple that outputs a row of _FIELD_NAMES.

    trip must be provided because it is not stored in StopTime.
    """
    result = []
    for fn in StopTime._FIELD_NAMES:
      if fn == 'trip_id':
        result.append(trip_id)
      else:
        result.append(getattr(self, fn) or '' )
    return tuple(result)

  def GetSqlValuesTuple(self, trip_id):
    result = []
    for fn in StopTime._SQL_FIELD_NAMES:
      if fn == 'trip_id':
        result.append(trip_id)
      else:
        # This might append None, which will be inserted into SQLite as NULL
        result.append(getattr(self, fn))
    return tuple(result)

  def GetTimeSecs(self):
    """Return the first of arrival_secs and departure_secs that is not None.
    If both are None return None."""
    if self.arrival_secs != None:
      return self.arrival_secs
    elif self.departure_secs != None:
      return self.departure_secs
    else:
      return None

  def __getattr__(self, name):
    if name == 'stop_id':
      return self.stop.stop_id
    elif name == 'arrival_time':
      return (self.arrival_secs != None and
          FormatSecondsSinceMidnight(self.arrival_secs) or '')
    elif name == 'departure_time':
      return (self.departure_secs != None and
          FormatSecondsSinceMidnight(self.departure_secs) or '')
    elif name == 'shape_dist_traveled':
      return ''
    raise AttributeError(name)


class Trip(GenericGTFSObject):
  _REQUIRED_FIELD_NAMES = ['route_id', 'service_id', 'trip_id']
  _FIELD_NAMES = _REQUIRED_FIELD_NAMES + [
    'trip_headsign', 'direction_id', 'block_id', 'shape_id'
    ]
  _FIELD_NAMES_HEADWAY = ['trip_id', 'start_time', 'end_time', 'headway_secs']
  _TABLE_NAME= "trips"

  def __init__(self, headsign=None, service_period=None,
               route=None, trip_id=None, field_dict=None):
    self._schedule = None
    self._headways = []  # [(start_time, end_time, headway_secs)]
    if not field_dict:
      field_dict = {}
      if headsign is not None:
        field_dict['trip_headsign'] = headsign
      if route:
        field_dict['route_id'] = route.route_id
      if trip_id is not None:
        field_dict['trip_id'] = trip_id
      if service_period is not None:
        field_dict['service_id'] = service_period.service_id
      # Earlier versions of transitfeed.py assigned self.service_period here
      # and allowed the caller to set self.service_id. Schedule.Validate
      # checked the service_id attribute if it was assigned and changed it to a
      # service_period attribute. Now only the service_id attribute is used and
      # it is validated by Trip.Validate.
      if service_period is not None:
        # For backwards compatibility
        self.service_id = service_period.service_id
    self.__dict__.update(field_dict)

  def GetFieldValuesTuple(self):
    return [getattr(self, fn) or '' for fn in Trip._FIELD_NAMES]

  def AddStopTime(self, stop, problems=None, schedule=None, **kwargs):
    """Add a stop to this trip. Stops must be added in the order visited.

    Args:
      stop: A Stop object
      kwargs: remaining keyword args passed to StopTime.__init__

    Returns:
      None
    """
    if problems is None:
      # TODO: delete this branch when StopTime.__init__ doesn't need a
      # ProblemReporter
      problems = default_problem_reporter
    stoptime = StopTime(problems=problems, stop=stop, **kwargs)
    self.AddStopTimeObject(stoptime, schedule)

  def _AddStopTimeObjectUnordered(self, stoptime, schedule):
    """Add StopTime object to this trip.

    The trip isn't checked for duplicate sequence numbers so it must be
    validated later."""
    cursor = schedule._connection.cursor()
    insert_query = "INSERT INTO stop_times (%s) VALUES (%s);" % (
       ','.join(StopTime._SQL_FIELD_NAMES),
       ','.join(['?'] * len(StopTime._SQL_FIELD_NAMES)))
    cursor = schedule._connection.cursor()
    cursor.execute(
        insert_query, stoptime.GetSqlValuesTuple(self.trip_id))

  def ReplaceStopTimeObject(self, stoptime, schedule=None):
    """Replace a StopTime object from this trip with the given one.

    Keys the StopTime object to be replaced by trip_id, stop_sequence
    and stop_id as 'stoptime', with the object 'stoptime'.
    """

    if schedule is None:
      schedule = self._schedule

    new_secs = stoptime.GetTimeSecs()
    cursor = schedule._connection.cursor()
    cursor.execute("DELETE FROM stop_times WHERE trip_id=? and "
                   "stop_sequence=? and stop_id=?",
                   (self.trip_id, stoptime.stop_sequence, stoptime.stop_id))
    if cursor.rowcount == 0:
      raise Error, 'Attempted replacement of StopTime object which does not exist'
    self._AddStopTimeObjectUnordered(stoptime, schedule)

  def AddStopTimeObject(self, stoptime, schedule=None, problems=None):
    """Add a StopTime object to the end of this trip.

    Args:
      stoptime: A StopTime object. Should not be reused in multiple trips.
      schedule: Schedule object containing this trip which must be
      passed to Trip.__init__ or here
      problems: ProblemReporter object for validating the StopTime in its new
      home

    Returns:
      None
    """
    if schedule is None:
      schedule = self._schedule
    if schedule is None:
      warnings.warn("No longer supported. _schedule attribute is  used to get "
                    "stop_times table", DeprecationWarning)
    if problems is None:
      problems = schedule.problem_reporter

    new_secs = stoptime.GetTimeSecs()
    cursor = schedule._connection.cursor()
    cursor.execute("SELECT max(stop_sequence), max(arrival_secs), "
                   "max(departure_secs) FROM stop_times WHERE trip_id=?",
                   (self.trip_id,))
    row = cursor.fetchone()
    if row[0] is None:
      # This is the first stop_time of the trip
      stoptime.stop_sequence = 1
      if new_secs == None:
        problems.OtherProblem(
            'No time for first StopTime of trip_id "%s"' % (self.trip_id,))
    else:
      stoptime.stop_sequence = row[0] + 1
      prev_secs = max(row[1], row[2])
      if new_secs != None and new_secs < prev_secs:
        problems.OtherProblem(
            'out of order stop time for stop_id=%s trip_id=%s %s < %s' %
            (EncodeUnicode(stoptime.stop_id), EncodeUnicode(self.trip_id),
             FormatSecondsSinceMidnight(new_secs),
             FormatSecondsSinceMidnight(prev_secs)))
    self._AddStopTimeObjectUnordered(stoptime, schedule)

  def GetTimeStops(self):
    """Return a list of (arrival_secs, departure_secs, stop) tuples.

    Caution: arrival_secs and departure_secs may be 0, a false value meaning a
    stop at midnight or None, a false value meaning the stop is untimed."""
    return [(st.arrival_secs, st.departure_secs, st.stop) for st in
            self.GetStopTimes()]

  def GetCountStopTimes(self):
    """Return the number of stops made by this trip."""
    cursor = self._schedule._connection.cursor()
    cursor.execute(
        'SELECT count(*) FROM stop_times WHERE trip_id=?', (self.trip_id,))
    return cursor.fetchone()[0]

  def GetTimeInterpolatedStops(self):
    """Return a list of (secs, stoptime, is_timepoint) tuples.

    secs will always be an int. If the StopTime object does not have explict
    times this method guesses using distance. stoptime is a StopTime object and
    is_timepoint is a bool.

    Raises:
      ValueError if this trip does not have the times needed to interpolate
    """
    rv = []

    stoptimes = self.GetStopTimes()
    # If there are no stoptimes [] is the correct return value but if the start
    # or end are missing times there is no correct return value.
    if not stoptimes:
      return []
    if (stoptimes[0].GetTimeSecs() is None or
        stoptimes[-1].GetTimeSecs() is None):
      raise ValueError("%s must have time at first and last stop" % (self))

    cur_timepoint = None
    next_timepoint = None
    distance_between_timepoints = 0
    distance_traveled_between_timepoints = 0

    for i, st in enumerate(stoptimes):
      if st.GetTimeSecs() != None:
        cur_timepoint = st
        distance_between_timepoints = 0
        distance_traveled_between_timepoints = 0
        if i + 1 < len(stoptimes):
          k = i + 1
          distance_between_timepoints += ApproximateDistanceBetweenStops(stoptimes[k-1].stop, stoptimes[k].stop)
          while stoptimes[k].GetTimeSecs() == None:
            k += 1
            distance_between_timepoints += ApproximateDistanceBetweenStops(stoptimes[k-1].stop, stoptimes[k].stop)
          next_timepoint = stoptimes[k]
        rv.append( (st.GetTimeSecs(), st, True) )
      else:
        distance_traveled_between_timepoints += ApproximateDistanceBetweenStops(stoptimes[i-1].stop, st.stop)
        distance_percent = distance_traveled_between_timepoints / distance_between_timepoints
        total_time = next_timepoint.GetTimeSecs() - cur_timepoint.GetTimeSecs()
        time_estimate = distance_percent * total_time + cur_timepoint.GetTimeSecs()
        rv.append( (int(round(time_estimate)), st, False) )

    return rv

  def ClearStopTimes(self):
    """Remove all stop times from this trip.

    StopTime objects previously returned by GetStopTimes are unchanged but are
    no longer associated with this trip.
    """
    cursor = self._schedule._connection.cursor()
    cursor.execute('DELETE FROM stop_times WHERE trip_id=?', (self.trip_id,))

  def GetStopTimes(self, problems=None):
    """Return a sorted list of StopTime objects for this trip."""
    # In theory problems=None should be safe because data from database has been
    # validated. See comment in _LoadStopTimes for why this isn't always true.
    cursor = self._schedule._connection.cursor()
    cursor.execute(
        'SELECT arrival_secs,departure_secs,stop_headsign,pickup_type,'
        'drop_off_type,shape_dist_traveled,stop_id,stop_sequence FROM '
        'stop_times WHERE '
        'trip_id=? ORDER BY stop_sequence', (self.trip_id,))
    stop_times = []
    for row in cursor.fetchall():
      stop = self._schedule.GetStop(row[6])
      stop_times.append(StopTime(problems=problems, stop=stop, arrival_secs=row[0],
                                 departure_secs=row[1],
                                 stop_headsign=row[2],
                                 pickup_type=row[3],
                                 drop_off_type=row[4],
                                 shape_dist_traveled=row[5],
                                 stop_sequence=row[7]))
    return stop_times

  def GetHeadwayStopTimes(self, problems=None):
    """Return a list of StopTime objects for each headway-based run.

    Returns:
      a list of list of StopTime objects. Each list of StopTime objects
      represents one run. If this trip doesn't have headways returns an empty
      list.
    """
    stoptimes_list = [] # list of stoptime lists to be returned
    stoptime_pattern = self.GetStopTimes()
    first_secs = stoptime_pattern[0].arrival_secs # first time of the trip
    # for each start time of a headway run
    for run_secs in self.GetHeadwayStartTimes():
      # stop time list for a headway run
      stoptimes = []
      # go through the pattern and generate stoptimes
      for st in stoptime_pattern:
        arrival_secs, departure_secs = None, None # default value if the stoptime is not timepoint
        if st.arrival_secs != None:
          arrival_secs = st.arrival_secs - first_secs + run_secs
        if st.departure_secs != None:
          departure_secs = st.departure_secs - first_secs + run_secs
        # append stoptime
        stoptimes.append(StopTime(problems=problems, stop=st.stop,
                                  arrival_secs=arrival_secs,
                                  departure_secs=departure_secs,
                                  stop_headsign=st.stop_headsign,
                                  pickup_type=st.pickup_type,
                                  drop_off_type=st.drop_off_type,
                                  shape_dist_traveled=st.shape_dist_traveled,
                                  stop_sequence=st.stop_sequence))
      # add stoptimes to the stoptimes_list
      stoptimes_list.append ( stoptimes )
    return stoptimes_list

  def GetStartTime(self, problems=default_problem_reporter):
    """Return the first time of the trip. TODO: For trips defined by frequency
    return the first time of the first trip."""
    cursor = self._schedule._connection.cursor()
    cursor.execute(
        'SELECT arrival_secs,departure_secs FROM stop_times WHERE '
        'trip_id=? ORDER BY stop_sequence LIMIT 1', (self.trip_id,))
    (arrival_secs, departure_secs) = cursor.fetchone()
    if arrival_secs != None:
      return arrival_secs
    elif departure_secs != None:
      return departure_secs
    else:
      problems.InvalidValue('departure_time', '',
                            'The first stop_time in trip %s is missing '
                            'times.' % self.trip_id)

  def GetHeadwayStartTimes(self):
    """Return a list of start time for each headway-based run.

    Returns:
      a sorted list of seconds since midnight, the start time of each run. If
      this trip doesn't have headways returns an empty list."""
    start_times = []
    # for each headway period of the trip
    for start_secs, end_secs, headway_secs in self.GetHeadwayPeriodTuples():
      # reset run secs to the start of the timeframe
      run_secs = start_secs
      while run_secs < end_secs:
        start_times.append(run_secs)
        # increment current run secs by headway secs
        run_secs += headway_secs
    return start_times

  def GetEndTime(self, problems=default_problem_reporter):
    """Return the last time of the trip. TODO: For trips defined by frequency
    return the last time of the last trip."""
    cursor = self._schedule._connection.cursor()
    cursor.execute(
        'SELECT arrival_secs,departure_secs FROM stop_times WHERE '
        'trip_id=? ORDER BY stop_sequence DESC LIMIT 1', (self.trip_id,))
    (arrival_secs, departure_secs) = cursor.fetchone()
    if departure_secs != None:
      return departure_secs
    elif arrival_secs != None:
      return arrival_secs
    else:
      problems.InvalidValue('arrival_time', '',
                            'The last stop_time in trip %s is missing '
                            'times.' % self.trip_id)

  def _GenerateStopTimesTuples(self):
    """Generator for rows of the stop_times file"""
    stoptimes = self.GetStopTimes()
    for i, st in enumerate(stoptimes):
      yield st.GetFieldValuesTuple(self.trip_id)

  def GetStopTimesTuples(self):
    results = []
    for time_tuple in self._GenerateStopTimesTuples():
      results.append(time_tuple)
    return results

  def GetPattern(self):
    """Return a tuple of Stop objects, in the order visited"""
    stoptimes = self.GetStopTimes()
    return tuple(st.stop for st in stoptimes)

  def AddHeadwayPeriod(self, start_time, end_time, headway_secs,
                       problem_reporter=default_problem_reporter):
    """Adds a period to this trip during which the vehicle travels
    at regular intervals (rather than specifying exact times for each stop).

    Args:
      start_time: The time at which this headway period starts, either in
          numerical seconds since midnight or as "HH:MM:SS" since midnight.
      end_time: The time at which this headway period ends, either in
          numerical seconds since midnight or as "HH:MM:SS" since midnight.
          This value should be larger than start_time.
      headway_secs: The amount of time, in seconds, between occurences of
          this trip.
      problem_reporter: Optional parameter that can be used to select
          how any errors in the other input parameters will be reported.
    Returns:
      None
    """
    if start_time == None or start_time == '':  # 0 is OK
      problem_reporter.MissingValue('start_time')
      return
    if isinstance(start_time, basestring):
      try:
        start_time = TimeToSecondsSinceMidnight(start_time)
      except Error:
        problem_reporter.InvalidValue('start_time', start_time)
        return
    elif start_time < 0:
      problem_reporter.InvalidValue('start_time', start_time)

    if end_time == None or end_time == '':
      problem_reporter.MissingValue('end_time')
      return
    if isinstance(end_time, basestring):
      try:
        end_time = TimeToSecondsSinceMidnight(end_time)
      except Error:
        problem_reporter.InvalidValue('end_time', end_time)
        return
    elif end_time < 0:
      problem_reporter.InvalidValue('end_time', end_time)
      return

    if not headway_secs:
      problem_reporter.MissingValue('headway_secs')
      return
    try:
      headway_secs = int(headway_secs)
    except ValueError:
      problem_reporter.InvalidValue('headway_secs', headway_secs)
      return

    if headway_secs <= 0:
      problem_reporter.InvalidValue('headway_secs', headway_secs)
      return

    if end_time <= start_time:
      problem_reporter.InvalidValue('end_time', end_time,
                                    'should be greater than start_time')

    self._headways.append((start_time, end_time, headway_secs))

  def ClearHeadwayPeriods(self):
    self._headways = []

  def _HeadwayOutputTuple(self, headway):
      return (self.trip_id,
              FormatSecondsSinceMidnight(headway[0]),
              FormatSecondsSinceMidnight(headway[1]),
              unicode(headway[2]))

  def GetHeadwayPeriodOutputTuples(self):
    tuples = []
    for headway in self._headways:
      tuples.append(self._HeadwayOutputTuple(headway))
    return tuples

  def GetHeadwayPeriodTuples(self):
    return self._headways

  def __getattr__(self, name):
    if name == 'service_period':
      assert self._schedule, "Must be in a schedule to get service_period"
      return self._schedule.GetServicePeriod(self.service_id)
    elif name == 'pattern_id':
      if '_pattern_id' not in self.__dict__:
        self.__dict__['_pattern_id'] = hash(self.GetPattern())
      return self.__dict__['_pattern_id']
    else:
      return GenericGTFSObject.__getattr__(self, name)

  def Validate(self, problems, validate_children=True):
    """Validate attributes of this object.

    Check that this object has all required values set to a valid value without
    reference to the rest of the schedule. If the _schedule attribute is set
    then check that references such as route_id and service_id are correct.

    Args:
      problems: A ProblemReporter object
      validate_children: if True and the _schedule attribute is set than call
                         ValidateChildren
    """
    if IsEmpty(self.route_id):
      problems.MissingValue('route_id')
    if 'service_period' in self.__dict__:
      # Some tests assign to the service_period attribute. Patch up self before
      # proceeding with validation. See also comment in Trip.__init__.
      self.service_id = self.__dict__['service_period'].service_id
      del self.service_period
    if IsEmpty(self.service_id):
      problems.MissingValue('service_id')
    if IsEmpty(self.trip_id):
      problems.MissingValue('trip_id')
    if hasattr(self, 'direction_id') and (not IsEmpty(self.direction_id)) and \
        (self.direction_id != '0') and (self.direction_id != '1'):
      problems.InvalidValue('direction_id', self.direction_id,
                            'direction_id must be "0" or "1"')
    if self._schedule:
      if self.shape_id and self.shape_id not in self._schedule._shapes:
        problems.InvalidValue('shape_id', self.shape_id)
      if self.route_id and self.route_id not in self._schedule.routes:
        problems.InvalidValue('route_id', self.route_id)
      if (self.service_id and
          self.service_id not in self._schedule.service_periods):
        problems.InvalidValue('service_id', self.service_id)

      if validate_children:
        self.ValidateChildren(problems)

  def ValidateChildren(self, problems):
    """Validate StopTimes and headways of this trip."""
    assert self._schedule, "Trip must be in a schedule to ValidateChildren"
    # TODO: validate distance values in stop times (if applicable)
    cursor = self._schedule._connection.cursor()
    cursor.execute("SELECT COUNT(stop_sequence) AS a FROM stop_times "
                   "WHERE trip_id=? GROUP BY stop_sequence HAVING a > 1",
                   (self.trip_id,))
    for row in cursor:
      problems.InvalidValue('stop_sequence', row[0],
                            'Duplicate stop_sequence in trip_id %s' %
                            self.trip_id)

    stoptimes = self.GetStopTimes(problems)
    if stoptimes:
      if stoptimes[0].arrival_time is None and stoptimes[0].departure_time is None:
        problems.OtherProblem(
          'No time for start of trip_id "%s""' % (self.trip_id))
      if stoptimes[-1].arrival_time is None and stoptimes[-1].departure_time is None:
        problems.OtherProblem(
          'No time for end of trip_id "%s""' % (self.trip_id))

      # Sorts the stoptimes by sequence and then checks that the arrival time
      # for each time point is after the departure time of the previous.
      stoptimes.sort(key=lambda x: x.stop_sequence)
      prev_departure = 0
      prev_stop = None
      prev_distance = None
      try:
        route_type = self._schedule.GetRoute(self.route_id).route_type
        max_speed = Route._ROUTE_TYPES[route_type]['max_speed']
      except KeyError, e:
        # If route_type cannot be found, assume it is 0 (Tram) for checking
        # speeds between stops.
        max_speed = Route._ROUTE_TYPES[0]['max_speed']
      for timepoint in stoptimes:
        # Distance should be a nonnegative float number, so it should be 
        # always larger than None.
        distance = timepoint.shape_dist_traveled
        if distance is not None:
          if distance > prev_distance and distance >= 0:
            prev_distance = distance
          else:
            if distance == prev_distance:
              type = TYPE_WARNING
            else:
              type = TYPE_ERROR
            problems.InvalidValue('stoptimes.shape_dist_traveled', distance,
                  'For the trip %s the stop %s has shape_dist_traveled=%s, '
                  'which should be larger than the previous ones. In this '
                  'case, the previous distance was %s.' % 
                  (self.trip_id, timepoint.stop_id, distance, prev_distance),
                  type=type)

        if timepoint.arrival_secs is not None:
          self._CheckSpeed(prev_stop, timepoint.stop, prev_departure,
                           timepoint.arrival_secs, max_speed, problems)

          if timepoint.arrival_secs >= prev_departure:
            prev_departure = timepoint.departure_secs
            prev_stop = timepoint.stop
          else:
            problems.OtherProblem('Timetravel detected! Arrival time '
                                  'is before previous departure '
                                  'at sequence number %s in trip %s' %
                                  (timepoint.stop_sequence, self.trip_id))

      if self.shape_id and self.shape_id in self._schedule._shapes:
        shape = self._schedule.GetShape(self.shape_id)
        max_shape_dist = shape.max_distance
        st = stoptimes[-1]
        if (st.shape_dist_traveled and
            st.shape_dist_traveled > max_shape_dist):
          problems.OtherProblem(
              'In stop_times.txt, the stop with trip_id=%s and '
              'stop_sequence=%d has shape_dist_traveled=%f, which is larger '
              'than the max shape_dist_traveled=%f of the corresponding '
              'shape (shape_id=%s)' %
              (self.trip_id, st.stop_sequence, st.shape_dist_traveled,
               max_shape_dist, self.shape_id), type=TYPE_WARNING)

        # shape_dist_traveled is valid in shape if max_shape_dist larger than
        # 0.
        if max_shape_dist > 0:
          for st in stoptimes:
            if st.shape_dist_traveled is None:
              continue
            pt = shape.GetPointWithDistanceTraveled(st.shape_dist_traveled)
            if pt:
              stop = self._schedule.GetStop(st.stop_id)
              distance = ApproximateDistance(stop.stop_lat, stop.stop_lon,
                                             pt[0], pt[1])
              if distance > MAX_DISTANCE_FROM_STOP_TO_SHAPE:
                problems.StopTooFarFromShapeWithDistTraveled(
                    self.trip_id, stop.stop_name, stop.stop_id, pt[2],
                    self.shape_id, distance, MAX_DISTANCE_FROM_STOP_TO_SHAPE)

    # O(n^2), but we don't anticipate many headway periods per trip
    for headway_index, headway in enumerate(self._headways[0:-1]):
      for other in self._headways[headway_index + 1:]:
        if (other[0] < headway[1]) and (other[1] > headway[0]):
          problems.OtherProblem('Trip contains overlapping headway periods '
                                '%s and %s' %
                                (self._HeadwayOutputTuple(headway),
                                 self._HeadwayOutputTuple(other)))

  def _CheckSpeed(self, prev_stop, next_stop, depart_time,
                  arrive_time, max_speed, problems):
    # Checks that the speed between two stops is not faster than max_speed
    if prev_stop != None:
      try:
        time_between_stops = arrive_time - depart_time
      except TypeError:
        return

      try:
        dist_between_stops = \
          ApproximateDistanceBetweenStops(next_stop, prev_stop)
      except TypeError, e:
          return

      if time_between_stops == 0:
        # HASTUS makes it hard to output GTFS with times to the nearest second;
        # it rounds times to the nearest minute. Therefore stop_times at the
        # same time ending in :00 are fairly common. These times off by no more
        # than 30 have not caused a problem. See
        # http://code.google.com/p/googletransitdatafeed/issues/detail?id=193
        # Show a warning if times are not rounded to the nearest minute or
        # distance is more than max_speed for one minute.
        if depart_time % 60 != 0 or dist_between_stops / 1000 * 60 > max_speed:
          problems.TooFastTravel(self.trip_id,
                                 prev_stop.stop_name,
                                 next_stop.stop_name,
                                 dist_between_stops,
                                 time_between_stops,
                                 speed=None,
                                 type=TYPE_WARNING)
        return
      # This needs floating point division for precision.
      speed_between_stops = ((float(dist_between_stops) / 1000) /
                                (float(time_between_stops) / 3600))
      if speed_between_stops > max_speed:
        problems.TooFastTravel(self.trip_id,
                               prev_stop.stop_name,
                               next_stop.stop_name,
                               dist_between_stops,
                               time_between_stops,
                               speed_between_stops,
                               type=TYPE_WARNING)

# TODO: move these into a separate file
class ISO4217(object):
  """Represents the set of currencies recognized by the ISO-4217 spec."""
  codes = {  # map of alpha code to numerical code
    'AED': 784, 'AFN': 971, 'ALL':   8, 'AMD':  51, 'ANG': 532, 'AOA': 973,
    'ARS':  32, 'AUD':  36, 'AWG': 533, 'AZN': 944, 'BAM': 977, 'BBD':  52,
    'BDT':  50, 'BGN': 975, 'BHD':  48, 'BIF': 108, 'BMD':  60, 'BND':  96,
    'BOB':  68, 'BOV': 984, 'BRL': 986, 'BSD':  44, 'BTN':  64, 'BWP':  72,
    'BYR': 974, 'BZD':  84, 'CAD': 124, 'CDF': 976, 'CHE': 947, 'CHF': 756,
    'CHW': 948, 'CLF': 990, 'CLP': 152, 'CNY': 156, 'COP': 170, 'COU': 970,
    'CRC': 188, 'CUP': 192, 'CVE': 132, 'CYP': 196, 'CZK': 203, 'DJF': 262,
    'DKK': 208, 'DOP': 214, 'DZD':  12, 'EEK': 233, 'EGP': 818, 'ERN': 232,
    'ETB': 230, 'EUR': 978, 'FJD': 242, 'FKP': 238, 'GBP': 826, 'GEL': 981,
    'GHC': 288, 'GIP': 292, 'GMD': 270, 'GNF': 324, 'GTQ': 320, 'GYD': 328,
    'HKD': 344, 'HNL': 340, 'HRK': 191, 'HTG': 332, 'HUF': 348, 'IDR': 360,
    'ILS': 376, 'INR': 356, 'IQD': 368, 'IRR': 364, 'ISK': 352, 'JMD': 388,
    'JOD': 400, 'JPY': 392, 'KES': 404, 'KGS': 417, 'KHR': 116, 'KMF': 174,
    'KPW': 408, 'KRW': 410, 'KWD': 414, 'KYD': 136, 'KZT': 398, 'LAK': 418,
    'LBP': 422, 'LKR': 144, 'LRD': 430, 'LSL': 426, 'LTL': 440, 'LVL': 428,
    'LYD': 434, 'MAD': 504, 'MDL': 498, 'MGA': 969, 'MKD': 807, 'MMK': 104,
    'MNT': 496, 'MOP': 446, 'MRO': 478, 'MTL': 470, 'MUR': 480, 'MVR': 462,
    'MWK': 454, 'MXN': 484, 'MXV': 979, 'MYR': 458, 'MZN': 943, 'NAD': 516,
    'NGN': 566, 'NIO': 558, 'NOK': 578, 'NPR': 524, 'NZD': 554, 'OMR': 512,
    'PAB': 590, 'PEN': 604, 'PGK': 598, 'PHP': 608, 'PKR': 586, 'PLN': 985,
    'PYG': 600, 'QAR': 634, 'ROL': 642, 'RON': 946, 'RSD': 941, 'RUB': 643,
    'RWF': 646, 'SAR': 682, 'SBD':  90, 'SCR': 690, 'SDD': 736, 'SDG': 938,
    'SEK': 752, 'SGD': 702, 'SHP': 654, 'SKK': 703, 'SLL': 694, 'SOS': 706,
    'SRD': 968, 'STD': 678, 'SYP': 760, 'SZL': 748, 'THB': 764, 'TJS': 972,
    'TMM': 795, 'TND': 788, 'TOP': 776, 'TRY': 949, 'TTD': 780, 'TWD': 901,
    'TZS': 834, 'UAH': 980, 'UGX': 800, 'USD': 840, 'USN': 997, 'USS': 998,
    'UYU': 858, 'UZS': 860, 'VEB': 862, 'VND': 704, 'VUV': 548, 'WST': 882,
    'XAF': 950, 'XAG': 961, 'XAU': 959, 'XBA': 955, 'XBB': 956, 'XBC': 957,
    'XBD': 958, 'XCD': 951, 'XDR': 960, 'XFO': None, 'XFU': None, 'XOF': 952,
    'XPD': 964, 'XPF': 953, 'XPT': 962, 'XTS': 963, 'XXX': 999, 'YER': 886,
    'ZAR': 710, 'ZMK': 894, 'ZWD': 716,
  }


class Fare(object):
  """Represents a fare type."""
  _REQUIRED_FIELD_NAMES = ['fare_id', 'price', 'currency_type',
                           'payment_method', 'transfers']
  _FIELD_NAMES = _REQUIRED_FIELD_NAMES + ['transfer_duration']

  def __init__(self,
               fare_id=None, price=None, currency_type=None,
               payment_method=None, transfers=None, transfer_duration=None,
               field_list=None):
    self.rules = []
    (self.fare_id, self.price, self.currency_type, self.payment_method,
     self.transfers, self.transfer_duration) = \
     (fare_id, price, currency_type, payment_method,
      transfers, transfer_duration)
    if field_list:
      (self.fare_id, self.price, self.currency_type, self.payment_method,
       self.transfers, self.transfer_duration) = field_list

    try:
      self.price = float(self.price)
    except (TypeError, ValueError):
      pass
    try:
      self.payment_method = int(self.payment_method)
    except (TypeError, ValueError):
      pass
    if self.transfers == None or self.transfers == "":
      self.transfers = None
    else:
      try:
        self.transfers = int(self.transfers)
      except (TypeError, ValueError):
        pass
    if self.transfer_duration == None or self.transfer_duration == "":
      self.transfer_duration = None
    else:
      try:
        self.transfer_duration = int(self.transfer_duration)
      except (TypeError, ValueError):
        pass

  def GetFareRuleList(self):
    return self.rules

  def ClearFareRules(self):
    self.rules = []

  def GetFieldValuesTuple(self):
    return [getattr(self, fn) for fn in Fare._FIELD_NAMES]

  def __getitem__(self, name):
    return getattr(self, name)

  def __eq__(self, other):
    if not other:
      return False

    if id(self) == id(other):
      return True

    if self.GetFieldValuesTuple() != other.GetFieldValuesTuple():
      return False

    self_rules = [r.GetFieldValuesTuple() for r in self.GetFareRuleList()]
    self_rules.sort()
    other_rules = [r.GetFieldValuesTuple() for r in other.GetFareRuleList()]
    other_rules.sort()
    return self_rules == other_rules

  def __ne__(self, other):
    return not self.__eq__(other)

  def Validate(self, problems=default_problem_reporter):
    if IsEmpty(self.fare_id):
      problems.MissingValue("fare_id")

    if self.price == None:
      problems.MissingValue("price")
    elif not isinstance(self.price, float) and not isinstance(self.price, int):
      problems.InvalidValue("price", self.price)
    elif self.price < 0:
      problems.InvalidValue("price", self.price)

    if IsEmpty(self.currency_type):
      problems.MissingValue("currency_type")
    elif self.currency_type not in ISO4217.codes:
      problems.InvalidValue("currency_type", self.currency_type)

    if self.payment_method == "" or self.payment_method == None:
      problems.MissingValue("payment_method")
    elif (not isinstance(self.payment_method, int) or
          self.payment_method not in range(0, 2)):
      problems.InvalidValue("payment_method", self.payment_method)

    if not ((self.transfers == None) or
            (isinstance(self.transfers, int) and
             self.transfers in range(0, 3))):
      problems.InvalidValue("transfers", self.transfers)

    if ((self.transfer_duration != None) and
        not isinstance(self.transfer_duration, int)):
      problems.InvalidValue("transfer_duration", self.transfer_duration)
    if self.transfer_duration and (self.transfer_duration < 0):
      problems.InvalidValue("transfer_duration", self.transfer_duration)
    if (self.transfer_duration and (self.transfer_duration > 0) and
        self.transfers == 0):
      problems.InvalidValue("transfer_duration", self.transfer_duration,
                            "can't have a nonzero transfer_duration for "
                            "a fare that doesn't allow transfers!")


class FareRule(object):
  """This class represents a rule that determines which itineraries a
  fare rule applies to."""
  _REQUIRED_FIELD_NAMES = ['fare_id']
  _FIELD_NAMES = _REQUIRED_FIELD_NAMES + ['route_id',
                                         'origin_id', 'destination_id',
                                         'contains_id']

  def __init__(self, fare_id=None, route_id=None,
               origin_id=None, destination_id=None, contains_id=None,
               field_list=None):
    (self.fare_id, self.route_id, self.origin_id, self.destination_id,
     self.contains_id) = \
     (fare_id, route_id, origin_id, destination_id, contains_id)
    if field_list:
      (self.fare_id, self.route_id, self.origin_id, self.destination_id,
       self.contains_id) = field_list

    # canonicalize non-content values as None
    if not self.route_id:
      self.route_id = None
    if not self.origin_id:
      self.origin_id = None
    if not self.destination_id:
      self.destination_id = None
    if not self.contains_id:
      self.contains_id = None

  def GetFieldValuesTuple(self):
    return [getattr(self, fn) for fn in FareRule._FIELD_NAMES]

  def __getitem__(self, name):
    return getattr(self, name)

  def __eq__(self, other):
    if not other:
      return False

    if id(self) == id(other):
      return True

    return self.GetFieldValuesTuple() == other.GetFieldValuesTuple()

  def __ne__(self, other):
    return not self.__eq__(other)


class Shape(object):
  """This class represents a geographic shape that corresponds to the route
  taken by one or more Trips."""
  _REQUIRED_FIELD_NAMES = ['shape_id', 'shape_pt_lat', 'shape_pt_lon',
                           'shape_pt_sequence']
  _FIELD_NAMES = _REQUIRED_FIELD_NAMES + ['shape_dist_traveled']
  def __init__(self, shape_id):
    # List of shape point tuple (lat, lng, shape_dist_traveled), where lat and
    # lon is the location of the shape point, and shape_dist_traveled is an
    # increasing metric representing the distance traveled along the shape.
    self.points = []
    # An ID that uniquely identifies a shape in the dataset.
    self.shape_id = shape_id
    # The max shape_dist_traveled of shape points in this shape.
    self.max_distance = 0
    # List of shape_dist_traveled of each shape point.
    self.distance = []

  def AddPoint(self, lat, lon, distance=None,
               problems=default_problem_reporter):

    try:
      lat = float(lat)
      if abs(lat) > 90.0:
        problems.InvalidValue('shape_pt_lat', lat)
        return
    except (TypeError, ValueError):
      problems.InvalidValue('shape_pt_lat', lat)
      return

    try:
      lon = float(lon)
      if abs(lon) > 180.0:
        problems.InvalidValue('shape_pt_lon', lon)
        return
    except (TypeError, ValueError):
      problems.InvalidValue('shape_pt_lon', lon)
      return

    if (abs(lat) < 1.0) and (abs(lon) < 1.0):
      problems.InvalidValue('shape_pt_lat', lat,
                            'Point location too close to 0, 0, which means '
                            'that it\'s probably an incorrect location.',
                            type=TYPE_WARNING)
      return

    if distance == '':  # canonicalizing empty string to None for comparison
      distance = None

    if distance != None:
      try:
        distance = float(distance)
        if (distance < self.max_distance and not
            (len(self.points) == 0 and distance == 0)):  # first one can be 0
          problems.InvalidValue('shape_dist_traveled', distance,
                                'Each subsequent point in a shape should '
                                'have a distance value that\'s at least as '
                                'large as the previous ones.  In this case, '
                                'the previous distance was %f.' % 
                                self.max_distance)
          return
        else:
          self.max_distance = distance
          self.distance.append(distance)
      except (TypeError, ValueError):
        problems.InvalidValue('shape_dist_traveled', distance,
                              'This value should be a positive number.')
        return

    self.points.append((lat, lon, distance))

  def ClearPoints(self):
    self.points = []

  def __eq__(self, other):
    if not other:
      return False

    if id(self) == id(other):
      return True

    return self.points == other.points

  def __ne__(self, other):
    return not self.__eq__(other)

  def __repr__(self):
    return "<Shape %s>" % self.__dict__

  def Validate(self, problems=default_problem_reporter):
    if IsEmpty(self.shape_id):
      problems.MissingValue('shape_id')

    if not self.points:
      problems.OtherProblem('The shape with shape_id "%s" contains no points.' %
                            self.shape_id, type=TYPE_WARNING)

  def GetPointWithDistanceTraveled(self, shape_dist_traveled):
    """Returns a point on the shape polyline with the input shape_dist_traveled.

    Args:
      shape_dist_traveled: The input shape_dist_traveled.

    Returns:
      The shape point as a tuple (lat, lng, shape_dist_traveled), where lat and
      lng is the location of the shape point, and shape_dist_traveled is an
      increasing metric representing the distance traveled along the shape.
      Returns None if there is data error in shape.
    """
    if not self.distance:
      return None
    if shape_dist_traveled <= self.distance[0]:
      return self.points[0]
    if shape_dist_traveled >= self.distance[-1]:
      return self.points[-1]

    index = bisect.bisect(self.distance, shape_dist_traveled)
    (lat0, lng0, dist0) = self.points[index - 1]
    (lat1, lng1, dist1) = self.points[index]

    # Interpolate if shape_dist_traveled does not equal to any of the point
    # in shape segment.
    # (lat0, lng0)          (lat, lng)           (lat1, lng1)
    # -----|--------------------|---------------------|------
    #    dist0          shape_dist_traveled         dist1
    #      \------- ca --------/ \-------- bc -------/
    #       \----------------- ba ------------------/
    ca = shape_dist_traveled - dist0
    bc = dist1 - shape_dist_traveled
    ba = bc + ca
    if ba == 0:
      # This only happens when there's data error in shapes and should have been
      # catched before. Check to avoid crash.
      return None
    # This won't work crossing longitude 180 and is only an approximation which
    # works well for short distance.
    lat = (lat1 * ca + lat0 * bc) / ba
    lng = (lng1 * ca + lng0 * bc) / ba
    return (lat, lng, shape_dist_traveled)


class ISO639(object):
  # Set of all the 2-letter ISO 639-1 language codes.
  codes_2letter = set([
    'aa', 'ab', 'ae', 'af', 'ak', 'am', 'an', 'ar', 'as', 'av', 'ay', 'az',
    'ba', 'be', 'bg', 'bh', 'bi', 'bm', 'bn', 'bo', 'br', 'bs', 'ca', 'ce',
    'ch', 'co', 'cr', 'cs', 'cu', 'cv', 'cy', 'da', 'de', 'dv', 'dz', 'ee',
    'el', 'en', 'eo', 'es', 'et', 'eu', 'fa', 'ff', 'fi', 'fj', 'fo', 'fr',
    'fy', 'ga', 'gd', 'gl', 'gn', 'gu', 'gv', 'ha', 'he', 'hi', 'ho', 'hr',
    'ht', 'hu', 'hy', 'hz', 'ia', 'id', 'ie', 'ig', 'ii', 'ik', 'io', 'is',
    'it', 'iu', 'ja', 'jv', 'ka', 'kg', 'ki', 'kj', 'kk', 'kl', 'km', 'kn',
    'ko', 'kr', 'ks', 'ku', 'kv', 'kw', 'ky', 'la', 'lb', 'lg', 'li', 'ln',
    'lo', 'lt', 'lu', 'lv', 'mg', 'mh', 'mi', 'mk', 'ml', 'mn', 'mo', 'mr',
    'ms', 'mt', 'my', 'na', 'nb', 'nd', 'ne', 'ng', 'nl', 'nn', 'no', 'nr',
    'nv', 'ny', 'oc', 'oj', 'om', 'or', 'os', 'pa', 'pi', 'pl', 'ps', 'pt',
    'qu', 'rm', 'rn', 'ro', 'ru', 'rw', 'sa', 'sc', 'sd', 'se', 'sg', 'si',
    'sk', 'sl', 'sm', 'sn', 'so', 'sq', 'sr', 'ss', 'st', 'su', 'sv', 'sw',
    'ta', 'te', 'tg', 'th', 'ti', 'tk', 'tl', 'tn', 'to', 'tr', 'ts', 'tt',
    'tw', 'ty', 'ug', 'uk', 'ur', 'uz', 've', 'vi', 'vo', 'wa', 'wo', 'xh',
    'yi', 'yo', 'za', 'zh', 'zu',
  ])


class Agency(GenericGTFSObject):
  """Represents an agency in a schedule.

  Callers may assign arbitrary values to instance attributes. __init__ makes no
  attempt at validating the attributes. Call Validate() to check that
  attributes are valid and the agency object is consistent with itself.

  Attributes:
    All attributes are strings.
  """
  _REQUIRED_FIELD_NAMES = ['agency_name', 'agency_url', 'agency_timezone']
  _FIELD_NAMES = _REQUIRED_FIELD_NAMES + ['agency_id', 'agency_lang',
                                          'agency_phone']
  _TABLE_NAME = 'agency'

  def __init__(self, name=None, url=None, timezone=None, id=None,
               field_dict=None, lang=None, **kwargs):
    """Initialize a new Agency object.

    Args:
      field_dict: A dictionary mapping attribute name to unicode string
      name: a string, ignored when field_dict is present
      url: a string, ignored when field_dict is present
      timezone: a string, ignored when field_dict is present
      id: a string, ignored when field_dict is present
      kwargs: arbitrary keyword arguments may be used to add attributes to the
        new object, ignored when field_dict is present
    """
    self._schedule = None

    if not field_dict:
      if name:
        kwargs['agency_name'] = name
      if url:
        kwargs['agency_url'] = url
      if timezone:
        kwargs['agency_timezone'] = timezone
      if id:
        kwargs['agency_id'] = id
      if lang:
        kwargs['agency_lang'] = lang
      field_dict = kwargs

    self.__dict__.update(field_dict)

  def Validate(self, problems=default_problem_reporter):
    """Validate attribute values and this object's internal consistency.

    Returns:
      True iff all validation checks passed.
    """
    found_problem = False
    for required in Agency._REQUIRED_FIELD_NAMES:
      if IsEmpty(getattr(self, required, None)):
        problems.MissingValue(required)
        found_problem = True

    if self.agency_url and not IsValidURL(self.agency_url):
      problems.InvalidValue('agency_url', self.agency_url)
      found_problem = True

    if (not IsEmpty(self.agency_lang) and
        self.agency_lang.lower() not in ISO639.codes_2letter):
      problems.InvalidValue('agency_lang', self.agency_lang)
      found_problem = True

    try:
      import pytz
      if self.agency_timezone not in pytz.common_timezones:
        problems.InvalidValue(
            'agency_timezone',
            self.agency_timezone,
            '"%s" is not a common timezone name according to pytz version %s' %
            (self.agency_timezone, pytz.VERSION))
        found_problem = True
    except ImportError:  # no pytz
      print ("Timezone not checked "
             "(install pytz package for timezone validation)")
    return not found_problem


class Transfer(object):
  """Represents a transfer in a schedule"""
  _REQUIRED_FIELD_NAMES = ['from_stop_id', 'to_stop_id', 'transfer_type']
  _FIELD_NAMES = _REQUIRED_FIELD_NAMES + ['min_transfer_time']

  def __init__(self, schedule=None, from_stop_id=None, to_stop_id=None, transfer_type=None,
               min_transfer_time=None, field_dict=None):
    if schedule is not None:
      self._schedule = weakref.proxy(schedule)  # See weakref comment at top
    else:
      self._schedule = None
    if field_dict:
      self.__dict__.update(field_dict)
    else:
      self.from_stop_id = from_stop_id
      self.to_stop_id = to_stop_id
      self.transfer_type = transfer_type
      self.min_transfer_time = min_transfer_time

    if getattr(self, 'transfer_type', None) in ("", None):
      # Use the default, recommended transfer, if attribute is not set or blank
      self.transfer_type = 0
    else:
      try:
        self.transfer_type = NonNegIntStringToInt(self.transfer_type)
      except (TypeError, ValueError):
        pass

    if hasattr(self, 'min_transfer_time'):
      try:
        self.min_transfer_time = NonNegIntStringToInt(self.min_transfer_time)
      except (TypeError, ValueError):
        pass
    else:
      self.min_transfer_time = None

  def GetFieldValuesTuple(self):
    return [getattr(self, fn) for fn in Transfer._FIELD_NAMES]

  def __getitem__(self, name):
    return getattr(self, name)

  def __eq__(self, other):
    if not other:
      return False

    if id(self) == id(other):
      return True

    return self.GetFieldValuesTuple() == other.GetFieldValuesTuple()

  def __ne__(self, other):
    return not self.__eq__(other)

  def __repr__(self):
    return "<Transfer %s>" % self.__dict__

  def Validate(self, problems=default_problem_reporter):
    if IsEmpty(self.from_stop_id):
      problems.MissingValue('from_stop_id')
    elif self._schedule:
      if self.from_stop_id not in self._schedule.stops.keys():
        problems.InvalidValue('from_stop_id', self.from_stop_id)

    if IsEmpty(self.to_stop_id):
      problems.MissingValue('to_stop_id')
    elif self._schedule:
      if self.to_stop_id not in self._schedule.stops.keys():
        problems.InvalidValue('to_stop_id', self.to_stop_id)

    if not IsEmpty(self.transfer_type):
      if (not isinstance(self.transfer_type, int)) or \
          (self.transfer_type not in range(0, 4)):
        problems.InvalidValue('transfer_type', self.transfer_type)

    if not IsEmpty(self.min_transfer_time):
      if (not isinstance(self.min_transfer_time, int)) or \
          self.min_transfer_time < 0:
        problems.InvalidValue('min_transfer_time', self.min_transfer_time)


class ServicePeriod(object):
  """Represents a service, which identifies a set of dates when one or more
  trips operate."""
  _DAYS_OF_WEEK = [
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
    'saturday', 'sunday'
    ]
  _FIELD_NAMES_REQUIRED = [
    'service_id', 'start_date', 'end_date'
    ] + _DAYS_OF_WEEK
  _FIELD_NAMES = _FIELD_NAMES_REQUIRED  # no optional fields in this one
  _FIELD_NAMES_CALENDAR_DATES = ['service_id', 'date', 'exception_type']

  def __init__(self, id=None, field_list=None):
    self.original_day_values = []
    if field_list:
      self.service_id = field_list[self._FIELD_NAMES.index('service_id')]
      self.day_of_week = [False] * len(self._DAYS_OF_WEEK)

      for day in self._DAYS_OF_WEEK:
        value = field_list[self._FIELD_NAMES.index(day)] or ''  # can be None
        self.original_day_values += [value.strip()]
        self.day_of_week[self._DAYS_OF_WEEK.index(day)] = (value == u'1')

      self.start_date = field_list[self._FIELD_NAMES.index('start_date')]
      self.end_date = field_list[self._FIELD_NAMES.index('end_date')]
    else:
      self.service_id = id
      self.day_of_week = [False] * 7
      self.start_date = None
      self.end_date = None
    self.date_exceptions = {}  # Map from 'YYYYMMDD' to 1 (add) or 2 (remove)

  def _IsValidDate(self, date):
    if re.match('^\d{8}$', date) == None:
      return False

    try:
      time.strptime(date, "%Y%m%d")
      return True
    except ValueError:
      return False

  def GetDateRange(self):
    """Return the range over which this ServicePeriod is valid.

    The range includes exception dates that add service outside of
    (start_date, end_date), but doesn't shrink the range if exception
    dates take away service at the edges of the range.

    Returns:
      A tuple of "YYYYMMDD" strings, (start date, end date) or (None, None) if
      no dates have been given.
    """
    start = self.start_date
    end = self.end_date

    for date in self.date_exceptions:
      if self.date_exceptions[date] == 2:
        continue
      if not start or (date < start):
        start = date
      if not end or (date > end):
        end = date
    if start is None:
      start = end
    elif end is None:
      end = start
    # If start and end are None we did a little harmless shuffling
    return (start, end)

  def GetCalendarFieldValuesTuple(self):
    """Return the tuple of calendar.txt values or None if this ServicePeriod
    should not be in calendar.txt ."""
    if self.start_date and self.end_date:
      return [getattr(self, fn) for fn in ServicePeriod._FIELD_NAMES]

  def GenerateCalendarDatesFieldValuesTuples(self):
    """Generates tuples of calendar_dates.txt values. Yield zero tuples if
    this ServicePeriod should not be in calendar_dates.txt ."""
    for date, exception_type in self.date_exceptions.items():
      yield (self.service_id, date, unicode(exception_type))

  def GetCalendarDatesFieldValuesTuples(self):
    """Return a list of date execeptions"""
    result = []
    for date_tuple in self.GenerateCalendarDatesFieldValuesTuples():
      result.append(date_tuple)
    result.sort()  # helps with __eq__
    return result

  def SetDateHasService(self, date, has_service=True, problems=None):
    if date in self.date_exceptions and problems:
      problems.DuplicateID(('service_id', 'date'),
                           (self.service_id, date),
                           type=TYPE_WARNING)
    self.date_exceptions[date] = has_service and 1 or 2

  def ResetDateToNormalService(self, date):
    if date in self.date_exceptions:
      del self.date_exceptions[date]

  def SetStartDate(self, start_date):
    """Set the first day of service as a string in YYYYMMDD format"""
    self.start_date = start_date

  def SetEndDate(self, end_date):
    """Set the last day of service as a string in YYYYMMDD format"""
    self.end_date = end_date

  def SetDayOfWeekHasService(self, dow, has_service=True):
    """Set service as running (or not) on a day of the week. By default the
    service does not run on any days.

    Args:
      dow: 0 for Monday through 6 for Sunday
      has_service: True if this service operates on dow, False if it does not.

    Returns:
      None
    """
    assert(dow >= 0 and dow < 7)
    self.day_of_week[dow] = has_service

  def SetWeekdayService(self, has_service=True):
    """Set service as running (or not) on all of Monday through Friday."""
    for i in range(0, 5):
      self.SetDayOfWeekHasService(i, has_service)

  def SetWeekendService(self, has_service=True):
    """Set service as running (or not) on Saturday and Sunday."""
    self.SetDayOfWeekHasService(5, has_service)
    self.SetDayOfWeekHasService(6, has_service)

  def SetServiceId(self, service_id):
    """Set the service_id for this schedule. Generally the default will
    suffice so you won't need to call this method."""
    self.service_id = service_id

  def IsActiveOn(self, date, date_object=None):
    """Test if this service period is active on a date.

    Args:
      date: a string of form "YYYYMMDD"
      date_object: a date object representing the same date as date.
                   This parameter is optional, and present only for performance
                   reasons.
                   If the caller constructs the date string from a date object
                   that date object can be passed directly, thus avoiding the 
                   costly conversion from string to date object.

    Returns:
      True iff this service is active on date.
    """
    if date in self.date_exceptions:
      if self.date_exceptions[date] == 1:
        return True
      else:
        return False
    if (self.start_date and self.end_date and self.start_date <= date and
        date <= self.end_date):
      if date_object is None:
        date_object = DateStringToDateObject(date)
      return self.day_of_week[date_object.weekday()]
    return False

  def ActiveDates(self):
    """Return dates this service period is active as a list of "YYYYMMDD"."""
    (earliest, latest) = self.GetDateRange()
    if earliest is None:
      return []
    dates = []
    date_it = DateStringToDateObject(earliest)
    date_end = DateStringToDateObject(latest)
    delta = datetime.timedelta(days=1)
    while date_it <= date_end:
      date_it_string = date_it.strftime("%Y%m%d")
      if self.IsActiveOn(date_it_string, date_it):
        dates.append(date_it_string)
      date_it = date_it + delta
    return dates

  def __getattr__(self, name):
    try:
      # Return 1 if value in day_of_week is True, 0 otherwise
      return (self.day_of_week[ServicePeriod._DAYS_OF_WEEK.index(name)]
              and 1 or 0)
    except KeyError:
      pass
    except ValueError:  # not a day of the week
      pass
    raise AttributeError(name)

  def __getitem__(self, name):
    return getattr(self, name)

  def __eq__(self, other):
    if not other:
      return False

    if id(self) == id(other):
      return True

    if (self.GetCalendarFieldValuesTuple() !=
        other.GetCalendarFieldValuesTuple()):
      return False

    if (self.GetCalendarDatesFieldValuesTuples() !=
        other.GetCalendarDatesFieldValuesTuples()):
      return False

    return True

  def __ne__(self, other):
    return not self.__eq__(other)

  def Validate(self, problems=default_problem_reporter):
    if IsEmpty(self.service_id):
      problems.MissingValue('service_id')
    # self.start_date/self.end_date is None in 3 cases:
    # ServicePeriod created by loader and
    #   1a) self.service_id wasn't in calendar.txt
    #   1b) calendar.txt didn't have a start_date/end_date column
    # ServicePeriod created directly and
    #   2) start_date/end_date wasn't set
    # In case 1a no problem is reported. In case 1b the missing required column
    # generates an error in _ReadCSV so this method should not report another
    # problem. There is no way to tell the difference between cases 1b and 2
    # so case 2 is ignored because making the feedvalidator pretty is more
    # important than perfect validation when an API users makes a mistake.
    start_date = None
    if self.start_date is not None:
      if IsEmpty(self.start_date):
        problems.MissingValue('start_date')
      elif self._IsValidDate(self.start_date):
        start_date = self.start_date
      else:
        problems.InvalidValue('start_date', self.start_date)
    end_date = None
    if self.end_date is not None:
      if IsEmpty(self.end_date):
        problems.MissingValue('end_date')
      elif self._IsValidDate(self.end_date):
        end_date = self.end_date
      else:
        problems.InvalidValue('end_date', self.end_date)
    if start_date and end_date and end_date < start_date:
      problems.InvalidValue('end_date', end_date,
                            'end_date of %s is earlier than '
                            'start_date of "%s"' %
                            (end_date, start_date))
    if self.original_day_values:
      index = 0
      for value in self.original_day_values:
        column_name = self._DAYS_OF_WEEK[index]
        if IsEmpty(value):
          problems.MissingValue(column_name)
        elif (value != u'0') and (value != '1'):
          problems.InvalidValue(column_name, value)
        index += 1
    if (True not in self.day_of_week and
        1 not in self.date_exceptions.values()):
      problems.OtherProblem('Service period with service_id "%s" '
                            'doesn\'t have service on any days '
                            'of the week.' % self.service_id,
                            type=TYPE_WARNING)
    for date in self.date_exceptions:
      if not self._IsValidDate(date):
        problems.InvalidValue('date', date)


class CsvUnicodeWriter:
  """
  Create a wrapper around a csv writer object which can safely write unicode
  values. Passes all arguments to csv.writer.
  """
  def __init__(self, *args, **kwargs):
    self.writer = csv.writer(*args, **kwargs)

  def writerow(self, row):
    """Write row to the csv file. Any unicode strings in row are encoded as
    utf-8."""
    encoded_row = []
    for s in row:
      if isinstance(s, unicode):
        encoded_row.append(s.encode("utf-8"))
      else:
        encoded_row.append(s)
    try:
      self.writer.writerow(encoded_row)
    except Exception, e:
      print 'error writing %s as %s' % (row, encoded_row)
      raise e

  def writerows(self, rows):
    """Write rows to the csv file. Any unicode strings in rows are encoded as
    utf-8."""
    for row in rows:
      self.writerow(row)

  def __getattr__(self, name):
    return getattr(self.writer, name)


class Schedule:
  """Represents a Schedule, a collection of stops, routes, trips and
  an agency.  This is the main class for this module."""

  def __init__(self, problem_reporter=default_problem_reporter,
               memory_db=True, check_duplicate_trips=False):
    # Map from table name to list of columns present in this schedule
    self._table_columns = {}

    self._agencies = {}
    self.stops = {}
    self.routes = {}
    self.trips = {}
    self.service_periods = {}
    self.fares = {}
    self.fare_zones = {}  # represents the set of all known fare zones
    self._shapes = {}  # shape_id to Shape
    self._transfers = []  # list of transfers
    self._default_service_period = None
    self._default_agency = None
    self.problem_reporter = problem_reporter
    self._check_duplicate_trips = check_duplicate_trips
    self.ConnectDb(memory_db)

  def AddTableColumn(self, table, column):
    """Add column to table if it is not already there."""
    if column not in self._table_columns[table]:
      self._table_columns[table].append(column)

  def AddTableColumns(self, table, columns):
    """Add columns to table if they are not already there.

    Args:
      table: table name as a string
      columns: an iterable of column names"""
    table_columns = self._table_columns.setdefault(table, [])
    for attr in columns:
      if attr not in table_columns:
        table_columns.append(attr)

  def GetTableColumns(self, table):
    """Return list of columns in a table."""
    return self._table_columns[table]

  def __del__(self):
    if hasattr(self, '_temp_db_filename'):
      os.remove(self._temp_db_filename)

  def ConnectDb(self, memory_db):
    if memory_db:
      self._connection = sqlite.connect(":memory:")
    else:
      try:
        self._temp_db_file = tempfile.NamedTemporaryFile()
        self._connection = sqlite.connect(self._temp_db_file.name)
      except sqlite.OperationalError:
        # Windows won't let a file be opened twice. mkstemp does not remove the
        # file when all handles to it are closed.
        self._temp_db_file = None
        (fd, self._temp_db_filename) = tempfile.mkstemp(".db")
        os.close(fd)
        self._connection = sqlite.connect(self._temp_db_filename)

    cursor = self._connection.cursor()
    cursor.execute("""CREATE TABLE stop_times (
                                           trip_id CHAR(50),
                                           arrival_secs INTEGER,
                                           departure_secs INTEGER,
                                           stop_id CHAR(50),
                                           stop_sequence INTEGER,
                                           stop_headsign VAR CHAR(100),
                                           pickup_type INTEGER,
                                           drop_off_type INTEGER,
                                           shape_dist_traveled FLOAT);""")
    cursor.execute("""CREATE INDEX trip_index ON stop_times (trip_id);""")
    cursor.execute("""CREATE INDEX stop_index ON stop_times (stop_id);""")

  def GetStopBoundingBox(self):
    return (min(s.stop_lat for s in self.stops.values()),
            min(s.stop_lon for s in self.stops.values()),
            max(s.stop_lat for s in self.stops.values()),
            max(s.stop_lon for s in self.stops.values()),
           )

  def AddAgency(self, name, url, timezone, agency_id=None):
    """Adds an agency to this schedule."""
    agency = Agency(name, url, timezone, agency_id)
    self.AddAgencyObject(agency)
    return agency

  def AddAgencyObject(self, agency, problem_reporter=None, validate=True):
    assert agency._schedule is None

    if not problem_reporter:
      problem_reporter = self.problem_reporter

    if agency.agency_id in self._agencies:
      problem_reporter.DuplicateID('agency_id', agency.agency_id)
      return

    self.AddTableColumns('agency', agency._ColumnNames())
    agency._schedule = weakref.proxy(self)

    if validate:
      agency.Validate(problem_reporter)
    self._agencies[agency.agency_id] = agency

  def GetAgency(self, agency_id):
    """Return Agency with agency_id or throw a KeyError"""
    return self._agencies[agency_id]

  def GetDefaultAgency(self):
    """Return the default Agency. If no default Agency has been set select the
    default depending on how many Agency objects are in the Schedule. If there
    are 0 make a new Agency the default, if there is 1 it becomes the default,
    if there is more than 1 then return None.
    """
    if not self._default_agency:
      if len(self._agencies) == 0:
        self.NewDefaultAgency()
      elif len(self._agencies) == 1:
        self._default_agency = self._agencies.values()[0]
    return self._default_agency

  def NewDefaultAgency(self, **kwargs):
    """Create a new Agency object and make it the default agency for this Schedule"""
    agency = Agency(**kwargs)
    if not agency.agency_id:
      agency.agency_id = FindUniqueId(self._agencies)
    self._default_agency = agency
    self.SetDefaultAgency(agency, validate=False)  # Blank agency won't validate
    return agency

  def SetDefaultAgency(self, agency, validate=True):
    """Make agency the default and add it to the schedule if not already added"""
    assert isinstance(agency, Agency)
    self._default_agency = agency
    if agency.agency_id not in self._agencies:
      self.AddAgencyObject(agency, validate=validate)

  def GetAgencyList(self):
    """Returns the list of Agency objects known to this Schedule."""
    return self._agencies.values()

  def GetServicePeriod(self, service_id):
    """Returns the ServicePeriod object with the given ID."""
    return self.service_periods[service_id]

  def GetDefaultServicePeriod(self):
    """Return the default ServicePeriod. If no default ServicePeriod has been
    set select the default depending on how many ServicePeriod objects are in
    the Schedule. If there are 0 make a new ServicePeriod the default, if there
    is 1 it becomes the default, if there is more than 1 then return None.
    """
    if not self._default_service_period:
      if len(self.service_periods) == 0:
        self.NewDefaultServicePeriod()
      elif len(self.service_periods) == 1:
        self._default_service_period = self.service_periods.values()[0]
    return self._default_service_period

  def NewDefaultServicePeriod(self):
    """Create a new ServicePeriod object, make it the default service period and
    return it. The default service period is used when you create a trip without
    providing an explict service period. """
    service_period = ServicePeriod()
    service_period.service_id = FindUniqueId(self.service_periods)
    # blank service won't validate in AddServicePeriodObject
    self.SetDefaultServicePeriod(service_period, validate=False)
    return service_period

  def SetDefaultServicePeriod(self, service_period, validate=True):
    assert isinstance(service_period, ServicePeriod)
    self._default_service_period = service_period
    if service_period.service_id not in self.service_periods:
      self.AddServicePeriodObject(service_period, validate=validate)

  def AddServicePeriodObject(self, service_period, problem_reporter=None,
                             validate=True):
    if not problem_reporter:
      problem_reporter = self.problem_reporter

    if service_period.service_id in self.service_periods:
      problem_reporter.DuplicateID('service_id', service_period.service_id)
      return

    if validate:
      service_period.Validate(problem_reporter)
    self.service_periods[service_period.service_id] = service_period

  def GetServicePeriodList(self):
    return self.service_periods.values()

  def GetDateRange(self):
    """Returns a tuple of (earliest, latest) dates on which the service
    periods in the schedule define service, in YYYYMMDD form."""

    ranges = [period.GetDateRange() for period in self.GetServicePeriodList()]
    starts = filter(lambda x: x, [item[0] for item in ranges])
    ends = filter(lambda x: x, [item[1] for item in ranges])

    if not starts or not ends:
      return (None, None)

    return (min(starts), max(ends))

  def GetServicePeriodsActiveEachDate(self, date_start, date_end):
    """Return a list of tuples (date, [period1, period2, ...]).

    For each date in the range [date_start, date_end) make list of each
    ServicePeriod object which is active.

    Args:
      date_start: The first date in the list, a date object
      date_end: The first date after the list, a date object

    Returns:
      A list of tuples. Each tuple contains a date object and a list of zero or
      more ServicePeriod objects.
    """
    date_it = date_start
    one_day = datetime.timedelta(days=1)
    date_service_period_list = []
    while date_it < date_end:
      periods_today = []
      date_it_string = date_it.strftime("%Y%m%d")
      for service in self.GetServicePeriodList():
        if service.IsActiveOn(date_it_string, date_it):
          periods_today.append(service)
      date_service_period_list.append((date_it, periods_today))
      date_it += one_day
    return date_service_period_list


  def AddStop(self, lat, lng, name):
    """Add a stop to this schedule.

    A new stop_id is created for this stop. Do not use this method unless all
    stops in this Schedule are created with it. See source for details.

    Args:
      lat: Latitude of the stop as a float or string
      lng: Longitude of the stop as a float or string
      name: Name of the stop, which will appear in the feed

    Returns:
      A new Stop object
    """
    # TODO: stop_id isn't guarenteed to be unique and conflicts are not
    # handled. Please fix.
    stop_id = unicode(len(self.stops))
    stop = Stop(stop_id=stop_id, lat=lat, lng=lng, name=name)
    self.AddStopObject(stop)
    return stop

  def AddStopObject(self, stop, problem_reporter=None):
    """Add Stop object to this schedule if stop_id is non-blank."""
    assert stop._schedule is None
    if not problem_reporter:
      problem_reporter = self.problem_reporter

    if not stop.stop_id:
      return

    if stop.stop_id in self.stops:
      problem_reporter.DuplicateID('stop_id', stop.stop_id)
      return

    stop._schedule = weakref.proxy(self)
    self.AddTableColumns('stops', stop._ColumnNames())
    self.stops[stop.stop_id] = stop
    if hasattr(stop, 'zone_id') and stop.zone_id:
      self.fare_zones[stop.zone_id] = True

  def GetStopList(self):
    return self.stops.values()

  def AddRoute(self, short_name, long_name, route_type):
    """Add a route to this schedule.

    Args:
      short_name: Short name of the route, such as "71L"
      long_name: Full name of the route, such as "NW 21st Ave/St Helens Rd"
      route_type: A type such as "Tram", "Subway" or "Bus"
    Returns:
      A new Route object
    """
    route_id = unicode(len(self.routes))
    route = Route(short_name=short_name, long_name=long_name,
                  route_type=route_type, route_id=route_id)
    route.agency_id = self.GetDefaultAgency().agency_id
    self.AddRouteObject(route)
    return route

  def AddRouteObject(self, route, problem_reporter=None):
    if not problem_reporter:
      problem_reporter = self.problem_reporter

    route.Validate(problem_reporter)

    if route.route_id in self.routes:
      problem_reporter.DuplicateID('route_id', route.route_id)
      return

    if route.agency_id not in self._agencies:
      if not route.agency_id and len(self._agencies) == 1:
        # we'll just assume that the route applies to the only agency
        pass
      else:
        problem_reporter.InvalidValue('agency_id', route.agency_id,
                                      'Route uses an unknown agency_id.')
        return

    self.AddTableColumns('routes', route._ColumnNames())
    route._schedule = weakref.proxy(self)
    self.routes[route.route_id] = route

  def GetRouteList(self):
    return self.routes.values()

  def GetRoute(self, route_id):
    return self.routes[route_id]

  def AddShapeObject(self, shape, problem_reporter=None):
    if not problem_reporter:
      problem_reporter = self.problem_reporter

    shape.Validate(problem_reporter)

    if shape.shape_id in self._shapes:
      problem_reporter.DuplicateID('shape_id', shape.shape_id)
      return

    self._shapes[shape.shape_id] = shape

  def GetShapeList(self):
    return self._shapes.values()

  def GetShape(self, shape_id):
    return self._shapes[shape_id]

  def AddTripObject(self, trip, problem_reporter=None, validate=True):
    if not problem_reporter:
      problem_reporter = self.problem_reporter

    if trip.trip_id in self.trips:
      problem_reporter.DuplicateID('trip_id', trip.trip_id)
      return

    self.AddTableColumns('trips', trip._ColumnNames())
    trip._schedule = weakref.proxy(self)
    self.trips[trip.trip_id] = trip

    # Call Trip.Validate after setting trip._schedule so that references
    # are checked. trip.ValidateChildren will be called directly by
    # schedule.Validate, after stop_times has been loaded.
    if validate:
      if not problem_reporter:
        problem_reporter = self.problem_reporter
      trip.Validate(problem_reporter, validate_children=False)
    try:
      self.routes[trip.route_id]._AddTripObject(trip)
    except KeyError:
      # Invalid route_id was reported in the Trip.Validate call above
      pass

  def GetTripList(self):
    return self.trips.values()

  def GetTrip(self, trip_id):
    return self.trips[trip_id]

  def AddFareObject(self, fare, problem_reporter=None):
    if not problem_reporter:
      problem_reporter = self.problem_reporter
    fare.Validate(problem_reporter)

    if fare.fare_id in self.fares:
      problem_reporter.DuplicateID('fare_id', fare.fare_id)
      return

    self.fares[fare.fare_id] = fare

  def GetFareList(self):
    return self.fares.values()

  def GetFare(self, fare_id):
    return self.fares[fare_id]

  def AddFareRuleObject(self, rule, problem_reporter=None):
    if not problem_reporter:
      problem_reporter = self.problem_reporter

    if IsEmpty(rule.fare_id):
      problem_reporter.MissingValue('fare_id')
      return

    if rule.route_id and rule.route_id not in self.routes:
      problem_reporter.InvalidValue('route_id', rule.route_id)
    if rule.origin_id and rule.origin_id not in self.fare_zones:
      problem_reporter.InvalidValue('origin_id', rule.origin_id)
    if rule.destination_id and rule.destination_id not in self.fare_zones:
      problem_reporter.InvalidValue('destination_id', rule.destination_id)
    if rule.contains_id and rule.contains_id not in self.fare_zones:
      problem_reporter.InvalidValue('contains_id', rule.contains_id)

    if rule.fare_id in self.fares:
      self.GetFare(rule.fare_id).rules.append(rule)
    else:
      problem_reporter.InvalidValue('fare_id', rule.fare_id,
                                    '(This fare_id doesn\'t correspond to any '
                                    'of the IDs defined in the '
                                    'fare attributes.)')

  def AddTransferObject(self, transfer, problem_reporter=None):
    assert transfer._schedule is None, "only add Transfer to a schedule once"
    transfer._schedule = weakref.proxy(self)  # See weakref comment at top
    if not problem_reporter:
      problem_reporter = self.problem_reporter

    transfer.Validate(problem_reporter)
    self._transfers.append(transfer)

  def GetTransferList(self):
    return self._transfers

  def GetStop(self, id):
    return self.stops[id]

  def GetFareZones(self):
    """Returns the list of all fare zones that have been identified by
    the stops that have been added."""
    return self.fare_zones.keys()

  def GetNearestStops(self, lat, lon, n=1):
    """Return the n nearest stops to lat,lon"""
    dist_stop_list = []
    for s in self.stops.values():
      # TODO: Use ApproximateDistanceBetweenStops?
      dist = (s.stop_lat - lat)**2 + (s.stop_lon - lon)**2
      if len(dist_stop_list) < n:
        bisect.insort(dist_stop_list, (dist, s))
      elif dist < dist_stop_list[-1][0]:
        bisect.insort(dist_stop_list, (dist, s))
        dist_stop_list.pop()  # Remove stop with greatest distance
    return [stop for dist, stop in dist_stop_list]

  def GetStopsInBoundingBox(self, north, east, south, west, n):
    """Return a sample of up to n stops in a bounding box"""
    stop_list = []
    for s in self.stops.values():
      if (s.stop_lat <= north and s.stop_lat >= south and
          s.stop_lon <= east and s.stop_lon >= west):
        stop_list.append(s)
        if len(stop_list) == n:
          break
    return stop_list

  def Load(self, feed_path, extra_validation=False):
    loader = Loader(feed_path, self, problems=self.problem_reporter,
                    extra_validation=extra_validation)
    loader.Load()

  def _WriteArchiveString(self, archive, filename, stringio):
    zi = zipfile.ZipInfo(filename)
    # See
    # http://stackoverflow.com/questions/434641/how-do-i-set-permissions-attributes-on-a-file-in-a-zip-file-using-pythons-zipf
    zi.external_attr = 0666 << 16L  # Set unix permissions to -rw-rw-rw
    # ZIP_DEFLATED requires zlib. zlib comes with Python 2.4 and 2.5
    zi.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(zi, stringio.getvalue())

  def WriteGoogleTransitFeed(self, file):
    """Output this schedule as a Google Transit Feed in file_name.

    Args:
      file: path of new feed file (a string) or a file-like object

    Returns:
      None
    """
    # Compression type given when adding each file
    archive = zipfile.ZipFile(file, 'w')

    if 'agency' in self._table_columns:
      agency_string = StringIO.StringIO()
      writer = CsvUnicodeWriter(agency_string)
      columns = self.GetTableColumns('agency')
      writer.writerow(columns)
      for a in self._agencies.values():
        writer.writerow([EncodeUnicode(a[c]) for c in columns])
      self._WriteArchiveString(archive, 'agency.txt', agency_string)

    calendar_dates_string = StringIO.StringIO()
    writer = CsvUnicodeWriter(calendar_dates_string)
    writer.writerow(ServicePeriod._FIELD_NAMES_CALENDAR_DATES)
    has_data = False
    for period in self.service_periods.values():
      for row in period.GenerateCalendarDatesFieldValuesTuples():
        has_data = True
        writer.writerow(row)
    wrote_calendar_dates = False
    if has_data:
      wrote_calendar_dates = True
      self._WriteArchiveString(archive, 'calendar_dates.txt',
                               calendar_dates_string)

    calendar_string = StringIO.StringIO()
    writer = CsvUnicodeWriter(calendar_string)
    writer.writerow(ServicePeriod._FIELD_NAMES)
    has_data = False
    for s in self.service_periods.values():
      row = s.GetCalendarFieldValuesTuple()
      if row:
        has_data = True
        writer.writerow(row)
    if has_data or not wrote_calendar_dates:
      self._WriteArchiveString(archive, 'calendar.txt', calendar_string)

    if 'stops' in self._table_columns:
      stop_string = StringIO.StringIO()
      writer = CsvUnicodeWriter(stop_string)
      columns = self.GetTableColumns('stops')
      writer.writerow(columns)
      for s in self.stops.values():
        writer.writerow([EncodeUnicode(s[c]) for c in columns])
      self._WriteArchiveString(archive, 'stops.txt', stop_string)

    if 'routes' in self._table_columns:
      route_string = StringIO.StringIO()
      writer = CsvUnicodeWriter(route_string)
      columns = self.GetTableColumns('routes')
      writer.writerow(columns)
      for r in self.routes.values():
        writer.writerow([EncodeUnicode(r[c]) for c in columns])
      self._WriteArchiveString(archive, 'routes.txt', route_string)

    if 'trips' in self._table_columns:
      trips_string = StringIO.StringIO()
      writer = CsvUnicodeWriter(trips_string)
      columns = self.GetTableColumns('trips')
      writer.writerow(columns)
      for t in self.trips.values():
        writer.writerow([EncodeUnicode(t[c]) for c in columns])
      self._WriteArchiveString(archive, 'trips.txt', trips_string)

    # write frequencies.txt (if applicable)
    headway_rows = []
    for trip in self.GetTripList():
      headway_rows += trip.GetHeadwayPeriodOutputTuples()
    if headway_rows:
      headway_string = StringIO.StringIO()
      writer = CsvUnicodeWriter(headway_string)
      writer.writerow(Trip._FIELD_NAMES_HEADWAY)
      writer.writerows(headway_rows)
      self._WriteArchiveString(archive, 'frequencies.txt', headway_string)

    # write fares (if applicable)
    if self.GetFareList():
      fare_string = StringIO.StringIO()
      writer = CsvUnicodeWriter(fare_string)
      writer.writerow(Fare._FIELD_NAMES)
      writer.writerows(f.GetFieldValuesTuple() for f in self.GetFareList())
      self._WriteArchiveString(archive, 'fare_attributes.txt', fare_string)

    # write fare rules (if applicable)
    rule_rows = []
    for fare in self.GetFareList():
      for rule in fare.GetFareRuleList():
        rule_rows.append(rule.GetFieldValuesTuple())
    if rule_rows:
      rule_string = StringIO.StringIO()
      writer = CsvUnicodeWriter(rule_string)
      writer.writerow(FareRule._FIELD_NAMES)
      writer.writerows(rule_rows)
      self._WriteArchiveString(archive, 'fare_rules.txt', rule_string)
    stop_times_string = StringIO.StringIO()
    writer = CsvUnicodeWriter(stop_times_string)
    writer.writerow(StopTime._FIELD_NAMES)
    for t in self.trips.values():
      writer.writerows(t._GenerateStopTimesTuples())
    self._WriteArchiveString(archive, 'stop_times.txt', stop_times_string)

    # write shapes (if applicable)
    shape_rows = []
    for shape in self.GetShapeList():
      seq = 1
      for (lat, lon, dist) in shape.points:
        shape_rows.append((shape.shape_id, lat, lon, seq, dist))
        seq += 1
    if shape_rows:
      shape_string = StringIO.StringIO()
      writer = CsvUnicodeWriter(shape_string)
      writer.writerow(Shape._FIELD_NAMES)
      writer.writerows(shape_rows)
      self._WriteArchiveString(archive, 'shapes.txt', shape_string)

    # write transfers (if applicable)
    if self.GetTransferList():
      transfer_string = StringIO.StringIO()
      writer = CsvUnicodeWriter(transfer_string)
      writer.writerow(Transfer._FIELD_NAMES)
      writer.writerows(f.GetFieldValuesTuple() for f in self.GetTransferList())
      self._WriteArchiveString(archive, 'transfers.txt', transfer_string)

    archive.close()

  def GenerateDateTripsDeparturesList(self, date_start, date_end):
    """Return a list of (date object, number of trips, number of departures).

    The list is generated for dates in the range [date_start, date_end).

    Args:
      date_start: The first date in the list, a date object
      date_end: The first date after the list, a date object

    Returns:
      a list of (date object, number of trips, number of departures) tuples
    """
    
    service_id_to_trips = defaultdict(lambda: 0)
    service_id_to_departures = defaultdict(lambda: 0)
    for trip in self.GetTripList():
      headway_start_times = trip.GetHeadwayStartTimes()
      if headway_start_times:
        trip_runs = len(headway_start_times)
      else:
        trip_runs = 1

      service_id_to_trips[trip.service_id] += trip_runs
      service_id_to_departures[trip.service_id] += (
          (trip.GetCountStopTimes() - 1) * trip_runs)

    date_services = self.GetServicePeriodsActiveEachDate(date_start, date_end)
    date_trips = []

    for date, services in date_services:
      day_trips = sum(service_id_to_trips[s.service_id] for s in services)
      day_departures = sum(
          service_id_to_departures[s.service_id] for s in services)
      date_trips.append((date, day_trips, day_departures))
    return date_trips

  def ValidateFeedStartAndExpirationDates(self, 
                                          problems, 
                                          first_date, 
                                          last_date, 
                                          today):
    """Validate the start and expiration dates of the feed.
       Issue a warning if it only starts in the future, or if
       it expires within 60 days.

    Args:
      problems: The problem reporter object
      first_date: A date object representing the first day the feed is active
      last_date: A date object representing the last day the feed is active
      today: A date object representing the date the validation is being run on

    Returns:
      None
    """
    warning_cutoff = today + datetime.timedelta(days=60)
    if last_date < warning_cutoff:
        problems.ExpirationDate(time.mktime(last_date.timetuple()))

    if first_date > today:
      problems.FutureService(time.mktime(first_date.timetuple()))

  def ValidateServiceGaps(self,
                          problems,
                          validation_start_date,
                          validation_end_date,
                          service_gap_interval):
    """Validate consecutive dates without service in the feed.
       Issue a warning if it finds service gaps of at least 
       "service_gap_interval" consecutive days in the date range
       [validation_start_date, last_service_date)

    Args:
      problems: The problem reporter object
      validation_start_date: A date object representing the date from which the
                             validation should take place
      validation_end_date: A date object representing the first day the feed is 
                        active
      service_gap_interval: An integer indicating how many consecutive days the 
                            service gaps need to have for a warning to be issued

    Returns:
      None
    """
    if service_gap_interval is None:
      return

    departures = self.GenerateDateTripsDeparturesList(validation_start_date,
                                                      validation_end_date)

    # The first day without service of the _current_ gap
    first_day_without_service = validation_start_date
    # The last day without service of the _current_ gap
    last_day_without_service = validation_start_date
    
    consecutive_days_without_service = 0

    for day_date, day_trips, _ in departures:
      if day_trips == 0:
        if consecutive_days_without_service == 0:
            first_day_without_service = day_date
        consecutive_days_without_service += 1
        last_day_without_service = day_date
      else:
        if consecutive_days_without_service >= service_gap_interval:
            problems.TooManyDaysWithoutService(first_day_without_service, 
                                               last_day_without_service, 
                                               consecutive_days_without_service)

        consecutive_days_without_service = 0
    
    # We have to check if there is a gap at the end of the specified date range
    if consecutive_days_without_service >= service_gap_interval:
      problems.TooManyDaysWithoutService(first_day_without_service, 
                                         last_day_without_service, 
                                         consecutive_days_without_service)

  def Validate(self,
               problems=None,
               validate_children=True,
               today=None,
               service_gap_interval=None):
    """Validates various holistic aspects of the schedule
       (mostly interrelationships between the various data sets)."""

    if today is None:
      today = datetime.date.today()

    if not problems:
      problems = self.problem_reporter

    (start_date, end_date) = self.GetDateRange()
    if not end_date or not start_date:
      problems.OtherProblem('This feed has no effective service dates!',
                            type=TYPE_WARNING)
    else:
        try:
          last_service_day = datetime.datetime(
              *(time.strptime(end_date, "%Y%m%d")[0:6])).date()
          first_service_day = datetime.datetime(
              *(time.strptime(start_date, "%Y%m%d")[0:6])).date()

        except ValueError:
          # Format of start_date and end_date checked in class ServicePeriod
          pass

        else:
          
          self.ValidateFeedStartAndExpirationDates(problems,
                                                   first_service_day,
                                                   last_service_day,
                                                   today)

          # We start checking for service gaps a bit in the past if the
          # feed was active then. See
          # http://code.google.com/p/googletransitdatafeed/issues/detail?id=188
          #
          # We subtract 1 from service_gap_interval so that if today has
          # service no warning is issued.
          #
          # Service gaps are searched for only up to one year from today
          if service_gap_interval is not None:
            service_gap_timedelta = datetime.timedelta(
                                        days=service_gap_interval - 1)
            one_year = datetime.timedelta(days=365)
            self.ValidateServiceGaps(
                problems,
                max(first_service_day,
                    today - service_gap_timedelta),
                min(last_service_day,
                    today + one_year),
                service_gap_interval)

    # TODO: Check Trip fields against valid values

    # Check for stops that aren't referenced by any trips and broken
    # parent_station references. Also check that the parent station isn't too
    # far from its child stops.
    for stop in self.stops.values():
      if validate_children:
        stop.Validate(problems)
      cursor = self._connection.cursor()
      cursor.execute("SELECT count(*) FROM stop_times WHERE stop_id=? LIMIT 1",
                     (stop.stop_id,))
      count = cursor.fetchone()[0]
      if stop.location_type == 0 and count == 0:
          problems.UnusedStop(stop.stop_id, stop.stop_name)
      elif stop.location_type == 1 and count != 0:
          problems.UsedStation(stop.stop_id, stop.stop_name)

      if stop.location_type != 1 and stop.parent_station:
        if stop.parent_station not in self.stops:
          problems.InvalidValue("parent_station",
                                EncodeUnicode(stop.parent_station),
                                "parent_station '%s' not found for stop_id "
                                "'%s' in stops.txt" %
                                (EncodeUnicode(stop.parent_station),
                                 EncodeUnicode(stop.stop_id)))
        elif self.stops[stop.parent_station].location_type != 1:
          problems.InvalidValue("parent_station",
                                EncodeUnicode(stop.parent_station),
                                "parent_station '%s' of stop_id '%s' must "
                                "have location_type=1 in stops.txt" %
                                (EncodeUnicode(stop.parent_station),
                                 EncodeUnicode(stop.stop_id)))
        else:
          parent_station = self.stops[stop.parent_station]
          distance = ApproximateDistanceBetweenStops(stop, parent_station)
          if distance > MAX_DISTANCE_BETWEEN_STOP_AND_PARENT_STATION_ERROR:
            problems.StopTooFarFromParentStation(
                stop.stop_id, stop.stop_name, parent_station.stop_id,
                parent_station.stop_name, distance, TYPE_ERROR)
          elif distance > MAX_DISTANCE_BETWEEN_STOP_AND_PARENT_STATION_WARNING:
            problems.StopTooFarFromParentStation(
                stop.stop_id, stop.stop_name, parent_station.stop_id,
                parent_station.stop_name, distance, TYPE_WARNING)

    #TODO: check that every station is used.
    # Then uncomment testStationWithoutReference.

    # Check for stops that might represent the same location (specifically,
    # stops that are less that 2 meters apart) First filter out stops without a
    # valid lat and lon. Then sort by latitude, then find the distance between
    # each pair of stations within 2 meters latitude of each other. This avoids
    # doing n^2 comparisons in the average case and doesn't need a spatial
    # index.
    sorted_stops = filter(lambda s: s.stop_lat and s.stop_lon,
                          self.GetStopList())
    sorted_stops.sort(key=(lambda x: x.stop_lat))
    TWO_METERS_LAT = 0.000018
    for index, stop in enumerate(sorted_stops[:-1]):
      index += 1
      while ((index < len(sorted_stops)) and
             ((sorted_stops[index].stop_lat - stop.stop_lat) < TWO_METERS_LAT)):
        distance  = ApproximateDistanceBetweenStops(stop, sorted_stops[index])
        if distance < 2:
          other_stop = sorted_stops[index]
          if stop.location_type == 0 and other_stop.location_type == 0:
            problems.StopsTooClose(
                EncodeUnicode(stop.stop_name),
                EncodeUnicode(stop.stop_id),
                EncodeUnicode(other_stop.stop_name),
                EncodeUnicode(other_stop.stop_id), distance)
          elif stop.location_type == 1 and other_stop.location_type == 1:
            problems.StationsTooClose(
                EncodeUnicode(stop.stop_name), EncodeUnicode(stop.stop_id),
                EncodeUnicode(other_stop.stop_name),
                EncodeUnicode(other_stop.stop_id), distance)
          elif (stop.location_type in (0, 1) and
                other_stop.location_type  in (0, 1)):
            if stop.location_type == 0 and other_stop.location_type == 1:
              this_stop = stop
              this_station = other_stop
            elif stop.location_type == 1 and other_stop.location_type == 0:
              this_stop = other_stop
              this_station = stop
            if this_stop.parent_station != this_station.stop_id:
              problems.DifferentStationTooClose(
                  EncodeUnicode(this_stop.stop_name),
                  EncodeUnicode(this_stop.stop_id),
                  EncodeUnicode(this_station.stop_name),
                  EncodeUnicode(this_station.stop_id), distance)
        index += 1

    # Check for multiple routes using same short + long name
    route_names = {}
    for route in self.routes.values():
      if validate_children:
        route.Validate(problems)
      short_name = ''
      if not IsEmpty(route.route_short_name):
        short_name = route.route_short_name.lower().strip()
      long_name = ''
      if not IsEmpty(route.route_long_name):
        long_name = route.route_long_name.lower().strip()
      name = (short_name, long_name)
      if name in route_names:
        problems.InvalidValue('route_long_name',
                              long_name,
                              'The same combination of '
                              'route_short_name and route_long_name '
                              'shouldn\'t be used for more than one '
                              'route, as it is for the for the two routes '
                              'with IDs "%s" and "%s".' %
                              (route.route_id, route_names[name].route_id),
                              type=TYPE_WARNING)
      else:
        route_names[name] = route

    stop_types = {} # a dict mapping stop_id to [route_id, route_type, is_match]
    trips = {} # a dict mapping tuple to (route_id, trip_id)
    for trip in sorted(self.trips.values()):
      if trip.route_id not in self.routes:
        continue
      route_type = self.GetRoute(trip.route_id).route_type
      arrival_times = []
      stop_ids = []
      for index, st in enumerate(trip.GetStopTimes(problems)):
        stop_id = st.stop.stop_id
        arrival_times.append(st.arrival_time)
        stop_ids.append(stop_id)
        # Check a stop if which belongs to both subway and bus.
        if (route_type == Route._ROUTE_TYPE_NAMES['Subway'] or
            route_type == Route._ROUTE_TYPE_NAMES['Bus']):
          if stop_id not in stop_types:
            stop_types[stop_id] = [trip.route_id, route_type, 0]
          elif (stop_types[stop_id][1] != route_type and
                stop_types[stop_id][2] == 0):
            stop_types[stop_id][2] = 1
            if stop_types[stop_id][1] == Route._ROUTE_TYPE_NAMES['Subway']:
              subway_route_id = stop_types[stop_id][0]
              bus_route_id = trip.route_id
            else:
              subway_route_id = trip.route_id
              bus_route_id = stop_types[stop_id][0]
            problems.StopWithMultipleRouteTypes(st.stop.stop_name, stop_id,
                                                subway_route_id, bus_route_id)

      # Check duplicate trips which go through the same stops with same
      # service and start times.
      if self._check_duplicate_trips:
        if not stop_ids or not arrival_times:
          continue
        key = (trip.service_id, min(arrival_times), str(stop_ids))
        if key not in trips:
          trips[key] = (trip.route_id, trip.trip_id)
        else:
          problems.DuplicateTrip(trips[key][1], trips[key][0], trip.trip_id,
                                 trip.route_id)

    # Check that routes' agency IDs are valid, if set
    for route in self.routes.values():
      if (not IsEmpty(route.agency_id) and
          not route.agency_id in self._agencies):
        problems.InvalidValue('agency_id',
                              route.agency_id,
                              'The route with ID "%s" specifies agency_id '
                              '"%s", which doesn\'t exist.' %
                              (route.route_id, route.agency_id))

    # Make sure all trips have stop_times
    # We're doing this here instead of in Trip.Validate() so that
    # Trips can be validated without error during the reading of trips.txt
    for trip in self.trips.values():
      trip.ValidateChildren(problems)
      count_stop_times = trip.GetCountStopTimes()
      if not count_stop_times:
        problems.OtherProblem('The trip with the trip_id "%s" doesn\'t have '
                              'any stop times defined.' % trip.trip_id,
                              type=TYPE_WARNING)
        if len(trip._headways) > 0:  # no stoptimes, but there are headways
          problems.OtherProblem('Frequencies defined, but no stop times given '
                                'in trip %s' % trip.trip_id, type=TYPE_ERROR)
      elif count_stop_times == 1:
        problems.OtherProblem('The trip with the trip_id "%s" only has one '
                              'stop on it; it should have at least one more '
                              'stop so that the riders can leave!' %
                              trip.trip_id, type=TYPE_WARNING)
      else:
        # These methods report InvalidValue if there's no first or last time
        trip.GetStartTime(problems=problems)
        trip.GetEndTime(problems=problems)

    # Check for unused shapes
    known_shape_ids = set(self._shapes.keys())
    used_shape_ids = set()
    for trip in self.GetTripList():
      used_shape_ids.add(trip.shape_id)
    unused_shape_ids = known_shape_ids - used_shape_ids
    if unused_shape_ids:
      problems.OtherProblem('The shapes with the following shape_ids aren\'t '
                            'used by any trips: %s' %
                            ', '.join(unused_shape_ids),
                            type=TYPE_WARNING)


# Map from literal string that should never be found in the csv data to a human
# readable description
INVALID_LINE_SEPARATOR_UTF8 = {
    "\x0c": "ASCII Form Feed 0x0C",
    # May be part of end of line, but not found elsewhere
    "\x0d": "ASCII Carriage Return 0x0D, \\r",
    "\xe2\x80\xa8": "Unicode LINE SEPARATOR U+2028",
    "\xe2\x80\xa9": "Unicode PARAGRAPH SEPARATOR U+2029",
    "\xc2\x85": "Unicode NEXT LINE SEPARATOR U+0085",
}

class EndOfLineChecker:
  """Wrapper for a file-like object that checks for consistent line ends.

  The check for consistent end of lines (all CR LF or all LF) only happens if
  next() is called until it raises StopIteration.
  """
  def __init__(self, f, name, problems):
    """Create new object.

    Args:
      f: file-like object to wrap
      name: name to use for f. StringIO objects don't have a name attribute.
      problems: a ProblemReporterBase object
    """
    self._f = f
    self._name = name
    self._crlf = 0
    self._crlf_examples = []
    self._lf = 0
    self._lf_examples = []
    self._line_number = 0  # first line will be number 1
    self._problems = problems

  def __iter__(self):
    return self

  def next(self):
    """Return next line without end of line marker or raise StopIteration."""
    try:
      next_line = self._f.next()
    except StopIteration:
      self._FinalCheck()
      raise

    self._line_number += 1
    m_eol = re.search(r"[\x0a\x0d]*$", next_line)
    if m_eol.group() == "\x0d\x0a":
      self._crlf += 1
      if self._crlf <= 5:
        self._crlf_examples.append(self._line_number)
    elif m_eol.group() == "\x0a":
      self._lf += 1
      if self._lf <= 5:
        self._lf_examples.append(self._line_number)
    elif m_eol.group() == "":
      # Should only happen at the end of the file
      try:
        self._f.next()
        raise RuntimeError("Unexpected row without new line sequence")
      except StopIteration:
        # Will be raised again when EndOfLineChecker.next() is next called
        pass
    else:
      self._problems.InvalidLineEnd(
        codecs.getencoder('string_escape')(m_eol.group())[0],
        (self._name, self._line_number))
    next_line_contents = next_line[0:m_eol.start()]
    for seq, name in INVALID_LINE_SEPARATOR_UTF8.items():
      if next_line_contents.find(seq) != -1:
        self._problems.OtherProblem(
          "Line contains %s" % name,
          context=(self._name, self._line_number))
    return next_line_contents

  def _FinalCheck(self):
    if self._crlf > 0 and self._lf > 0:
      crlf_plural = self._crlf > 1 and "s" or ""
      crlf_lines = ", ".join(["%s" % e for e in self._crlf_examples])
      if self._crlf > len(self._crlf_examples):
        crlf_lines += ", ..."
      lf_plural = self._lf > 1 and "s" or ""
      lf_lines = ", ".join(["%s" % e for e in self._lf_examples])
      if self._lf > len(self._lf_examples):
        lf_lines += ", ..."

      self._problems.OtherProblem(
          "Found %d CR LF \"\\r\\n\" line end%s (line%s %s) and "
          "%d LF \"\\n\" line end%s (line%s %s). A file must use a "
          "consistent line end." % (self._crlf, crlf_plural, crlf_plural,
                                   crlf_lines, self._lf, lf_plural,
                                   lf_plural, lf_lines),
          (self._name,))
      # Prevent _FinalCheck() from reporting the problem twice, in the unlikely
      # case that it is run twice
      self._crlf = 0
      self._lf = 0


# Filenames specified in GTFS spec
KNOWN_FILENAMES = [
  'agency.txt',
  'stops.txt',
  'routes.txt',
  'trips.txt',
  'stop_times.txt',
  'calendar.txt',
  'calendar_dates.txt',
  'fare_attributes.txt',
  'fare_rules.txt',
  'shapes.txt',
  'frequencies.txt',
  'transfers.txt',
]

class Loader:
  def __init__(self,
               feed_path=None,
               schedule=None,
               problems=default_problem_reporter,
               extra_validation=False,
               load_stop_times=True,
               memory_db=True,
               zip=None,
               check_duplicate_trips=False):
    """Initialize a new Loader object.

    Args:
      feed_path: string path to a zip file or directory
      schedule: a Schedule object or None to have one created
      problems: a ProblemReporter object, the default reporter raises an
        exception for each problem
      extra_validation: True if you would like extra validation
      load_stop_times: load the stop_times table, used to speed load time when
        times are not needed. The default is True.
      memory_db: if creating a new Schedule object use an in-memory sqlite
        database instead of creating one in a temporary file
      zip: a zipfile.ZipFile object, optionally used instead of path
    """
    if not schedule:
      schedule = Schedule(problem_reporter=problems, memory_db=memory_db,
                          check_duplicate_trips=check_duplicate_trips)
    self._extra_validation = extra_validation
    self._schedule = schedule
    self._problems = problems
    self._path = feed_path
    self._zip = zip
    self._load_stop_times = load_stop_times

  def _DetermineFormat(self):
    """Determines whether the feed is in a form that we understand, and
       if so, returns True."""
    if self._zip:
      # If zip was passed to __init__ then path isn't used
      assert not self._path
      return True

    if not isinstance(self._path, basestring) and hasattr(self._path, 'read'):
      # A file-like object, used for testing with a StringIO file
      self._zip = zipfile.ZipFile(self._path, mode='r')
      return True

    if not os.path.exists(self._path):
      self._problems.FeedNotFound(self._path)
      return False

    if self._path.endswith('.zip'):
      try:
        self._zip = zipfile.ZipFile(self._path, mode='r')
      except IOError:  # self._path is a directory
        pass
      except zipfile.BadZipfile:
        self._problems.UnknownFormat(self._path)
        return False

    if not self._zip and not os.path.isdir(self._path):
      self._problems.UnknownFormat(self._path)
      return False

    return True

  def _GetFileNames(self):
    """Returns a list of file names in the feed."""
    if self._zip:
      return self._zip.namelist()
    else:
      return os.listdir(self._path)

  def _CheckFileNames(self):
    filenames = self._GetFileNames()
    for feed_file in filenames:
      if feed_file not in KNOWN_FILENAMES:
        if not feed_file.startswith('.'):
          # Don't worry about .svn files and other hidden files
          # as this will break the tests.
          self._problems.UnknownFile(feed_file)

  def _GetUtf8Contents(self, file_name):
    """Check for errors in file_name and return a string for csv reader."""
    contents = self._FileContents(file_name)
    if not contents:  # Missing file
      return

    # Check for errors that will prevent csv.reader from working
    if len(contents) >= 2 and contents[0:2] in (codecs.BOM_UTF16_BE,
        codecs.BOM_UTF16_LE):
      self._problems.FileFormat("appears to be encoded in utf-16", (file_name, ))
      # Convert and continue, so we can find more errors
      contents = codecs.getdecoder('utf-16')(contents)[0].encode('utf-8')

    null_index = contents.find('\0')
    if null_index != -1:
      # It is easier to get some surrounding text than calculate the exact
      # row_num
      m = re.search(r'.{,20}\0.{,20}', contents, re.DOTALL)
      self._problems.FileFormat(
          "contains a null in text \"%s\" at byte %d" %
          (codecs.getencoder('string_escape')(m.group()), null_index + 1),
          (file_name, ))
      return

    # strip out any UTF-8 Byte Order Marker (otherwise it'll be
    # treated as part of the first column name, causing a mis-parse)
    contents = contents.lstrip(codecs.BOM_UTF8)
    return contents

  def _ReadCsvDict(self, file_name, all_cols, required):
    """Reads lines from file_name, yielding a dict of unicode values."""
    assert file_name.endswith(".txt")
    table_name = file_name[0:-4]
    contents = self._GetUtf8Contents(file_name)
    if not contents:
      return

    eol_checker = EndOfLineChecker(StringIO.StringIO(contents),
                                   file_name, self._problems)
    # The csv module doesn't provide a way to skip trailing space, but when I
    # checked 15/675 feeds had trailing space in a header row and 120 had spaces
    # after fields. Space after header fields can cause a serious parsing
    # problem, so warn. Space after body fields can cause a problem time,
    # integer and id fields; they will be validated at higher levels.
    reader = csv.reader(eol_checker, skipinitialspace=True)

    raw_header = reader.next()
    header_occurrences = defaultdict(lambda: 0)
    header = []
    valid_columns = []  # Index into raw_header and raw_row
    for i, h in enumerate(raw_header):
      h_stripped = h.strip()
      if not h_stripped:
        self._problems.CsvSyntax(
            description="The header row should not contain any blank values. "
                        "The corresponding column will be skipped for the "
                        "entire file.",
            context=(file_name, 1, [''] * len(raw_header), raw_header),
            type=TYPE_ERROR)
        continue
      elif h != h_stripped:
        self._problems.CsvSyntax(
            description="The header row should not contain any "
                        "space characters.",
            context=(file_name, 1, [''] * len(raw_header), raw_header),
            type=TYPE_WARNING)
      header.append(h_stripped)
      valid_columns.append(i)
      header_occurrences[h_stripped] += 1

    for name, count in header_occurrences.items():
      if count > 1:
        self._problems.DuplicateColumn(
            header=name,
            file_name=file_name,
            count=count)

    self._schedule._table_columns[table_name] = header

    # check for unrecognized columns, which are often misspellings
    unknown_cols = set(header) - set(all_cols)
    if len(unknown_cols) == len(header):
      self._problems.CsvSyntax(
            description="The header row did not contain any known column "
                        "names. The file is most likely missing the header row "
                        "or not in the expected CSV format.",
            context=(file_name, 1, [''] * len(raw_header), raw_header),
            type=TYPE_ERROR)
    else:
      for col in unknown_cols:
        # this is provided in order to create a nice colored list of
        # columns in the validator output
        context = (file_name, 1, [''] * len(header), header)
        self._problems.UnrecognizedColumn(file_name, col, context)

    missing_cols = set(required) - set(header)
    for col in missing_cols:
      # this is provided in order to create a nice colored list of
      # columns in the validator output
      context = (file_name, 1, [''] * len(header), header)
      self._problems.MissingColumn(file_name, col, context)

    line_num = 1  # First line read by reader.next() above
    for raw_row in reader:
      line_num += 1
      if len(raw_row) == 0:  # skip extra empty lines in file
        continue

      if len(raw_row) > len(raw_header):
        self._problems.OtherProblem('Found too many cells (commas) in line '
                                    '%d of file "%s".  Every row in the file '
                                    'should have the same number of cells as '
                                    'the header (first line) does.' %
                                    (line_num, file_name),
                                    (file_name, line_num),
                                    type=TYPE_WARNING)

      if len(raw_row) < len(raw_header):
        self._problems.OtherProblem('Found missing cells (commas) in line '
                                    '%d of file "%s".  Every row in the file '
                                    'should have the same number of cells as '
                                    'the header (first line) does.' %
                                    (line_num, file_name),
                                    (file_name, line_num),
                                    type=TYPE_WARNING)

      # raw_row is a list of raw bytes which should be valid utf-8. Convert each
      # valid_columns of raw_row into Unicode.
      valid_values = []
      unicode_error_columns = []  # index of valid_values elements with an error
      for i in valid_columns:
        try:
          valid_values.append(raw_row[i].decode('utf-8'))
        except UnicodeDecodeError:
          # Replace all invalid characters with REPLACEMENT CHARACTER (U+FFFD)
          valid_values.append(codecs.getdecoder("utf8")
                              (raw_row[i], errors="replace")[0])
          unicode_error_columns.append(len(valid_values) - 1)
        except IndexError:
          break

      # The error report may contain a dump of all values in valid_values so
      # problems can not be reported until after converting all of raw_row to
      # Unicode.
      for i in unicode_error_columns:
        self._problems.InvalidValue(header[i], valid_values[i],
                                    'Unicode error',
                                    (file_name, line_num,
                                     valid_values, header))


      d = dict(zip(header, valid_values))
      yield (d, line_num, header, valid_values)

  # TODO: Add testing for this specific function
  def _ReadCSV(self, file_name, cols, required):
    """Reads lines from file_name, yielding a list of unicode values
    corresponding to the column names in cols."""
    contents = self._GetUtf8Contents(file_name)
    if not contents:
      return

    eol_checker = EndOfLineChecker(StringIO.StringIO(contents),
                                   file_name, self._problems)
    reader = csv.reader(eol_checker)  # Use excel dialect

    header = reader.next()
    header = map(lambda x: x.strip(), header)  # trim any whitespace
    header_occurrences = defaultdict(lambda: 0)
    for column_header in header:
      header_occurrences[column_header] += 1

    for name, count in header_occurrences.items():
      if count > 1:
        self._problems.DuplicateColumn(
            header=name,
            file_name=file_name,
            count=count)

    # check for unrecognized columns, which are often misspellings
    unknown_cols = set(header).difference(set(cols))
    for col in unknown_cols:
      # this is provided in order to create a nice colored list of
      # columns in the validator output
      context = (file_name, 1, [''] * len(header), header)
      self._problems.UnrecognizedColumn(file_name, col, context)

    col_index = [-1] * len(cols)
    for i in range(len(cols)):
      if cols[i] in header:
        col_index[i] = header.index(cols[i])
      elif cols[i] in required:
        self._problems.MissingColumn(file_name, cols[i])

    row_num = 1
    for row in reader:
      row_num += 1
      if len(row) == 0:  # skip extra empty lines in file
        continue

      if len(row) > len(header):
        self._problems.OtherProblem('Found too many cells (commas) in line '
                                    '%d of file "%s".  Every row in the file '
                                    'should have the same number of cells as '
                                    'the header (first line) does.' %
                                    (row_num, file_name), (file_name, row_num),
                                    type=TYPE_WARNING)

      if len(row) < len(header):
        self._problems.OtherProblem('Found missing cells (commas) in line '
                                    '%d of file "%s".  Every row in the file '
                                    'should have the same number of cells as '
                                    'the header (first line) does.' %
                                    (row_num, file_name), (file_name, row_num),
                                    type=TYPE_WARNING)

      result = [None] * len(cols)
      unicode_error_columns = []  # A list of column numbers with an error
      for i in range(len(cols)):
        ci = col_index[i]
        if ci >= 0:
          if len(row) <= ci:  # handle short CSV rows
            result[i] = u''
          else:
            try:
              result[i] = row[ci].decode('utf-8').strip()
            except UnicodeDecodeError:
              # Replace all invalid characters with
              # REPLACEMENT CHARACTER (U+FFFD)
              result[i] = codecs.getdecoder("utf8")(row[ci],
                                                    errors="replace")[0].strip()
              unicode_error_columns.append(i)

      for i in unicode_error_columns:
        self._problems.InvalidValue(cols[i], result[i],
                                    'Unicode error',
                                    (file_name, row_num, result, cols))
      yield (result, row_num, cols)

  def _HasFile(self, file_name):
    """Returns True if there's a file in the current feed with the
       given file_name in the current feed."""
    if self._zip:
      return file_name in self._zip.namelist()
    else:
      file_path = os.path.join(self._path, file_name)
      return os.path.exists(file_path) and os.path.isfile(file_path)

  def _FileContents(self, file_name):
    results = None
    if self._zip:
      try:
        results = self._zip.read(file_name)
      except KeyError:  # file not found in archve
        self._problems.MissingFile(file_name)
        return None
    else:
      try:
        data_file = open(os.path.join(self._path, file_name), 'rb')
        results = data_file.read()
      except IOError:  # file not found
        self._problems.MissingFile(file_name)
        return None

    if not results:
      self._problems.EmptyFile(file_name)
    return results

  def _LoadAgencies(self):
    for (d, row_num, header, row) in self._ReadCsvDict('agency.txt',
                                              Agency._FIELD_NAMES,
                                              Agency._REQUIRED_FIELD_NAMES):
      self._problems.SetFileContext('agency.txt', row_num, row, header)
      agency = Agency(field_dict=d)
      self._schedule.AddAgencyObject(agency, self._problems)
      self._problems.ClearContext()

  def _LoadStops(self):
    for (d, row_num, header, row) in self._ReadCsvDict(
                                         'stops.txt',
                                         Stop._FIELD_NAMES,
                                         Stop._REQUIRED_FIELD_NAMES):
      self._problems.SetFileContext('stops.txt', row_num, row, header)

      stop = Stop(field_dict=d)
      stop.Validate(self._problems)
      self._schedule.AddStopObject(stop, self._problems)

      self._problems.ClearContext()

  def _LoadRoutes(self):
    for (d, row_num, header, row) in self._ReadCsvDict(
                                         'routes.txt',
                                         Route._FIELD_NAMES,
                                         Route._REQUIRED_FIELD_NAMES):
      self._problems.SetFileContext('routes.txt', row_num, row, header)

      route = Route(field_dict=d)
      self._schedule.AddRouteObject(route, self._problems)

      self._problems.ClearContext()

  def _LoadCalendar(self):
    file_name = 'calendar.txt'
    file_name_dates = 'calendar_dates.txt'
    if not self._HasFile(file_name) and not self._HasFile(file_name_dates):
      self._problems.MissingFile(file_name)
      return

    # map period IDs to (period object, (file_name, row_num, row, cols))
    periods = {}

    # process calendar.txt
    if self._HasFile(file_name):
      has_useful_contents = False
      for (row, row_num, cols) in \
              self._ReadCSV(file_name,
                            ServicePeriod._FIELD_NAMES,
                            ServicePeriod._FIELD_NAMES_REQUIRED):
        context = (file_name, row_num, row, cols)
        self._problems.SetFileContext(*context)

        period = ServicePeriod(field_list=row)

        if period.service_id in periods:
          self._problems.DuplicateID('service_id', period.service_id)
        else:
          periods[period.service_id] = (period, context)
        self._problems.ClearContext()

    # process calendar_dates.txt
    if self._HasFile(file_name_dates):
      # ['service_id', 'date', 'exception_type']
      fields = ServicePeriod._FIELD_NAMES_CALENDAR_DATES
      for (row, row_num, cols) in self._ReadCSV(file_name_dates,
                                                fields, fields):
        context = (file_name_dates, row_num, row, cols)
        self._problems.SetFileContext(*context)

        service_id = row[0]

        period = None
        if service_id in periods:
          period = periods[service_id][0]
        else:
          period = ServicePeriod(service_id)
          periods[period.service_id] = (period, context)

        exception_type = row[2]
        if exception_type == u'1':
          period.SetDateHasService(row[1], True, self._problems)
        elif exception_type == u'2':
          period.SetDateHasService(row[1], False, self._problems)
        else:
          self._problems.InvalidValue('exception_type', exception_type)
        self._problems.ClearContext()

    # Now insert the periods into the schedule object, so that they're
    # validated with both calendar and calendar_dates info present
    for period, context in periods.values():
      self._problems.SetFileContext(*context)
      self._schedule.AddServicePeriodObject(period, self._problems)
      self._problems.ClearContext()

  def _LoadShapes(self):
    if not self._HasFile('shapes.txt'):
      return

    shapes = {}  # shape_id to tuple
    for (row, row_num, cols) in self._ReadCSV('shapes.txt',
                                              Shape._FIELD_NAMES,
                                              Shape._REQUIRED_FIELD_NAMES):
      file_context = ('shapes.txt', row_num, row, cols)
      self._problems.SetFileContext(*file_context)

      (shape_id, lat, lon, seq, dist) = row
      if IsEmpty(shape_id):
        self._problems.MissingValue('shape_id')
        continue
      try:
        seq = int(seq)
      except (TypeError, ValueError):
        self._problems.InvalidValue('shape_pt_sequence', seq,
                                    'Value should be a number (0 or higher)')
        continue

      shapes.setdefault(shape_id, []).append((seq, lat, lon, dist, file_context))
      self._problems.ClearContext()

    for shape_id, points in shapes.items():
      shape = Shape(shape_id)
      points.sort()
      if points and points[0][0] < 0:
        self._problems.InvalidValue('shape_pt_sequence', points[0][0],
                                    'In shape %s, a negative sequence number '
                                    '%d was found; sequence numbers should be '
                                    '0 or higher.' % (shape_id, points[0][0]))

      last_seq = None
      for (seq, lat, lon, dist, file_context) in points:
        if (seq == last_seq):
          self._problems.SetFileContext(*file_context)
          self._problems.InvalidValue('shape_pt_sequence', seq,
                                      'The sequence number %d occurs more '
                                      'than once in shape %s.' %
                                      (seq, shape_id))
        last_seq = seq
        shape.AddPoint(lat, lon, dist, self._problems)
        self._problems.ClearContext()

      self._schedule.AddShapeObject(shape, self._problems)

  def _LoadTrips(self):
    for (d, row_num, header, row) in self._ReadCsvDict(
                                         'trips.txt',
                                         Trip._FIELD_NAMES,
                                         Trip._REQUIRED_FIELD_NAMES):
      self._problems.SetFileContext('trips.txt', row_num, row, header)

      trip = Trip(field_dict=d)
      self._schedule.AddTripObject(trip, self._problems)

      self._problems.ClearContext()

  def _LoadFares(self):
    if not self._HasFile('fare_attributes.txt'):
      return
    for (row, row_num, cols) in self._ReadCSV('fare_attributes.txt',
                                              Fare._FIELD_NAMES,
                                              Fare._REQUIRED_FIELD_NAMES):
      self._problems.SetFileContext('fare_attributes.txt', row_num, row, cols)

      fare = Fare(field_list=row)
      self._schedule.AddFareObject(fare, self._problems)

      self._problems.ClearContext()

  def _LoadFareRules(self):
    if not self._HasFile('fare_rules.txt'):
      return
    for (row, row_num, cols) in self._ReadCSV('fare_rules.txt',
                                              FareRule._FIELD_NAMES,
                                              FareRule._REQUIRED_FIELD_NAMES):
      self._problems.SetFileContext('fare_rules.txt', row_num, row, cols)

      rule = FareRule(field_list=row)
      self._schedule.AddFareRuleObject(rule, self._problems)

      self._problems.ClearContext()

  def _LoadHeadways(self):
    file_name = 'frequencies.txt'
    if not self._HasFile(file_name):  # headways are an optional feature
      return

    # ['trip_id', 'start_time', 'end_time', 'headway_secs']
    fields = Trip._FIELD_NAMES_HEADWAY
    modified_trips = {}
    for (row, row_num, cols) in self._ReadCSV(file_name, fields, fields):
      self._problems.SetFileContext(file_name, row_num, row, cols)
      (trip_id, start_time, end_time, headway_secs) = row
      try:
        trip = self._schedule.GetTrip(trip_id)
        trip.AddHeadwayPeriod(start_time, end_time, headway_secs,
                              self._problems)
        modified_trips[trip_id] = trip
      except KeyError:
        self._problems.InvalidValue('trip_id', trip_id)
      self._problems.ClearContext()

    for trip in modified_trips.values():
      trip.Validate(self._problems)

  def _LoadStopTimes(self):
    for (row, row_num, cols) in self._ReadCSV('stop_times.txt',
                                              StopTime._FIELD_NAMES,
                                              StopTime._REQUIRED_FIELD_NAMES):
      file_context = ('stop_times.txt', row_num, row, cols)
      self._problems.SetFileContext(*file_context)

      (trip_id, arrival_time, departure_time, stop_id, stop_sequence,
         stop_headsign, pickup_type, drop_off_type, shape_dist_traveled) = row

      try:
        sequence = int(stop_sequence)
      except (TypeError, ValueError):
        self._problems.InvalidValue('stop_sequence', stop_sequence,
                                    'This should be a number.')
        continue
      if sequence < 0:
        self._problems.InvalidValue('stop_sequence', sequence,
                                    'Sequence numbers should be 0 or higher.')

      if stop_id not in self._schedule.stops:
        self._problems.InvalidValue('stop_id', stop_id,
                                    'This value wasn\'t defined in stops.txt')
        continue
      stop = self._schedule.stops[stop_id]
      if trip_id not in self._schedule.trips:
        self._problems.InvalidValue('trip_id', trip_id,
                                    'This value wasn\'t defined in trips.txt')
        continue
      trip = self._schedule.trips[trip_id]

      # If self._problems.Report returns then StopTime.__init__ will return
      # even if the StopTime object has an error. Thus this code may add a
      # StopTime that didn't validate to the database.
      # Trip.GetStopTimes then tries to make a StopTime from the invalid data
      # and calls the problem reporter for errors. An ugly solution is to
      # wrap problems and a better solution is to move all validation out of
      # __init__. For now make sure Trip.GetStopTimes gets a problem reporter
      # when called from Trip.Validate.
      stop_time = StopTime(self._problems, stop, arrival_time,
                           departure_time, stop_headsign,
                           pickup_type, drop_off_type,
                           shape_dist_traveled, stop_sequence=sequence)
      trip._AddStopTimeObjectUnordered(stop_time, self._schedule)
      self._problems.ClearContext()

    # stop_times are validated in Trip.ValidateChildren, called by
    # Schedule.Validate

  def _LoadTransfers(self):
    file_name = 'transfers.txt'
    if not self._HasFile(file_name):  # transfers are an optional feature
      return
    for (d, row_num, header, row) in self._ReadCsvDict(file_name,
                                              Transfer._FIELD_NAMES,
                                              Transfer._REQUIRED_FIELD_NAMES):
      self._problems.SetFileContext(file_name, row_num, row, header)
      transfer = Transfer(field_dict=d)
      self._schedule.AddTransferObject(transfer, self._problems)
      self._problems.ClearContext()

  def Load(self):
    self._problems.ClearContext()
    if not self._DetermineFormat():
      return self._schedule

    self._CheckFileNames()

    self._LoadAgencies()
    self._LoadStops()
    self._LoadRoutes()
    self._LoadCalendar()
    self._LoadShapes()
    self._LoadTrips()
    self._LoadHeadways()
    if self._load_stop_times:
      self._LoadStopTimes()
    self._LoadFares()
    self._LoadFareRules()
    self._LoadTransfers()

    if self._zip:
      self._zip.close()
      self._zip = None

    if self._extra_validation:
      self._schedule.Validate(self._problems, validate_children=False)

    return self._schedule


class ShapeLoader(Loader):
  """A subclass of Loader that only loads the shapes from a GTFS file."""

  def __init__(self, *args, **kwargs):
    """Initialize a new ShapeLoader object.

    See Loader.__init__ for argument documentation.
    """
    Loader.__init__(self, *args, **kwargs)

  def Load(self):
    self._LoadShapes()
    return self._schedule
