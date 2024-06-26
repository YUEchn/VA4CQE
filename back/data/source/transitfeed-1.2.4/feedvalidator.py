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


"""Validates a GTFS file.

For usage information run feedvalidator.py --help
"""

import bisect
import codecs
import datetime
from transitfeed.util import defaultdict
import optparse
import os
import os.path
import re
import socket
import sys
import time
import transitfeed
from transitfeed import TYPE_ERROR, TYPE_WARNING
from urllib2 import Request, urlopen, HTTPError, URLError
from transitfeed import util
import webbrowser

SVN_TAG_URL = 'http://googletransitdatafeed.googlecode.com/svn/tags/'


def MaybePluralizeWord(count, word):
  if count == 1:
    return word
  else:
    return word + 's'


def PrettyNumberWord(count, word):
  return '%d %s' % (count, MaybePluralizeWord(count, word))


def UnCamelCase(camel):
  return re.sub(r'([a-z])([A-Z])', r'\1 \2', camel)


def ProblemCountText(error_count, warning_count):
  results = []
  if error_count:
    results.append(PrettyNumberWord(error_count, 'error'))
  if warning_count:
    results.append(PrettyNumberWord(warning_count, 'warning'))

  return ' and '.join(results)


def CalendarSummary(schedule):
  today = datetime.date.today()
  summary_end_date = today + datetime.timedelta(days=60)
  start_date, end_date = schedule.GetDateRange()

  if not start_date or not end_date:
    return {}
  
  try:
    start_date_object = transitfeed.DateStringToDateObject(start_date)
    end_date_object = transitfeed.DateStringToDateObject(end_date)
  except ValueError:
    return {}

  # Get the list of trips only during the period the feed is active.
  # As such we have to check if it starts in the future and/or if
  # if it ends in less than 60 days.
  date_trips_departures = schedule.GenerateDateTripsDeparturesList(
                              max(today, start_date_object),
                              min(summary_end_date, end_date_object))

  if not date_trips_departures:
    return {}

  # Check that the dates which will be shown in summary agree with these
  # calculations. Failure implies a bug which should be fixed. It isn't good
  # for users to discover assertion failures but means it will likely be fixed.
  assert start_date <= date_trips_departures[0][0].strftime("%Y%m%d")
  assert end_date >= date_trips_departures[-1][0].strftime("%Y%m%d")

  # Generate a map from int number of trips in a day to a list of date objects
  # with that many trips. The list of dates is sorted.
  trips_dates = defaultdict(lambda: [])
  trips = 0
  for date, day_trips, day_departures in date_trips_departures:
    trips += day_trips
    trips_dates[day_trips].append(date)
  mean_trips = trips / len(date_trips_departures)
  max_trips = max(trips_dates.keys())
  min_trips = min(trips_dates.keys())

  calendar_summary = {}
  calendar_summary['mean_trips'] = mean_trips
  calendar_summary['max_trips'] = max_trips
  calendar_summary['max_trips_dates'] = FormatDateList(trips_dates[max_trips])
  calendar_summary['min_trips'] = min_trips
  calendar_summary['min_trips_dates'] = FormatDateList(trips_dates[min_trips])
  calendar_summary['date_trips_departures'] = date_trips_departures
  calendar_summary['date_summary_range'] = "%s to %s" % (
      date_trips_departures[0][0].strftime("%a %b %d"),
      date_trips_departures[-1][0].strftime("%a %b %d"))

  return calendar_summary


def FormatDateList(dates):
  if not dates:
    return "0 service dates"

  formatted = [d.strftime("%a %b %d") for d in dates[0:3]]
  if len(dates) > 3:
    formatted.append("...")
  return "%s (%s)" % (PrettyNumberWord(len(dates), "service date"),
                      ", ".join(formatted))


def MaxVersion(versions):
  versions = filter(None, versions)
  versions.sort(lambda x,y: -cmp([int(item) for item in x.split('.')],
                                 [int(item) for item in y.split('.')]))
  if len(versions) > 0:
    return versions[0]


class CountingConsoleProblemReporter(transitfeed.ProblemReporter):
  def __init__(self):
    transitfeed.ProblemReporter.__init__(self)
    self._error_count = 0
    self._warning_count = 0

  def _Report(self, e):
    transitfeed.ProblemReporter._Report(self, e)
    if e.IsError():
      self._error_count += 1
    else:
      self._warning_count += 1

  def ErrorCount(self):
    return self._error_count

  def WarningCount(self):
    return self._warning_count

  def FormatCount(self):
    return ProblemCountText(self.ErrorCount(), self.WarningCount())

  def HasIssues(self):
    return self.ErrorCount() or self.WarningCount()


class BoundedProblemList(object):
  """A list of one type of ExceptionWithContext objects with bounded size."""
  def __init__(self, size_bound):
    self._count = 0
    self._exceptions = []
    self._size_bound = size_bound

  def Add(self, e):
    self._count += 1
    try:
      bisect.insort(self._exceptions, e)
    except TypeError:
      # The base class ExceptionWithContext raises this exception in __cmp__
      # to signal that an object is not comparable. Instead of keeping the most
      # significant issue keep the first reported.
      if self._count <= self._size_bound:
        self._exceptions.append(e)
    else:
      # self._exceptions is in order. Drop the least significant if the list is
      # now too long.
      if self._count > self._size_bound:
        del self._exceptions[-1]

  def _GetDroppedCount(self):
    return self._count - len(self._exceptions)

  def __repr__(self):
    return "<BoundedProblemList %s>" % repr(self._exceptions)

  count = property(lambda s: s._count)
  dropped_count = property(_GetDroppedCount)
  problems = property(lambda s: s._exceptions)


class LimitPerTypeProblemReporter(transitfeed.ProblemReporter):
  def __init__(self, limit_per_type):
    transitfeed.ProblemReporter.__init__(self)

    # {TYPE_WARNING: {"ClassName": BoundedProblemList()}}
    self._type_to_name_to_problist = {
      TYPE_WARNING: defaultdict(lambda: BoundedProblemList(limit_per_type)),
      TYPE_ERROR: defaultdict(lambda: BoundedProblemList(limit_per_type))
    }

  def HasIssues(self):
    return (self._type_to_name_to_problist[TYPE_ERROR] or
            self._type_to_name_to_problist[TYPE_WARNING])

  def _Report(self, e):
    self._type_to_name_to_problist[e.GetType()][e.__class__.__name__].Add(e)

  def ErrorCount(self):
    error_sets = self._type_to_name_to_problist[TYPE_ERROR].values()
    return sum(map(lambda v: v.count, error_sets))

  def WarningCount(self):
    warning_sets = self._type_to_name_to_problist[TYPE_WARNING].values()
    return sum(map(lambda v: v.count, warning_sets))

  def ProblemList(self, problem_type, class_name):
    """Return the BoundedProblemList object for given type and class."""
    return self._type_to_name_to_problist[problem_type][class_name]

  def ProblemListMap(self, problem_type):
    """Return the map from class name to BoundedProblemList object."""
    return self._type_to_name_to_problist[problem_type]


class HTMLCountingProblemReporter(LimitPerTypeProblemReporter):
  def FormatType(self, f, level_name, class_problist):
    """Write the HTML dumping all problems of one type.

    Args:
      f: file object open for writing
      level_name: string such as "Error" or "Warning"
      class_problist: sequence of tuples (class name,
          BoundedProblemList object)
    """
    class_problist.sort()
    output = []
    for classname, problist in class_problist:
      output.append('<h4 class="issueHeader"><a name="%s%s">%s</a></h4><ul>\n' %
                    (level_name, classname, UnCamelCase(classname)))
      for e in problist.problems:
        self.FormatException(e, output)
      if problist.dropped_count:
        output.append('<li>and %d more of this type.' %
                      (problist.dropped_count))
      output.append('</ul>\n')
    f.write(''.join(output))

  def FormatTypeSummaryTable(self, level_name, name_to_problist):
    """Return an HTML table listing the number of problems by class name.

    Args:
      level_name: string such as "Error" or "Warning"
      name_to_problist: dict mapping class name to an BoundedProblemList object

    Returns:
      HTML in a string
    """
    output = []
    output.append('<table>')
    for classname in sorted(name_to_problist.keys()):
      problist = name_to_problist[classname]
      human_name = MaybePluralizeWord(problist.count, UnCamelCase(classname))
      output.append('<tr><td>%d</td><td><a href="#%s%s">%s</a></td></tr>\n' %
                    (problist.count, level_name, classname, human_name))
    output.append('</table>\n')
    return ''.join(output)

  def FormatException(self, e, output):
    """Append HTML version of e to list output."""
    d = e.GetDictToFormat()
    for k in ('file_name', 'feedname', 'column_name'):
      if k in d.keys():
        d[k] = '<code>%s</code>' % d[k]
    problem_text = e.FormatProblem(d).replace('\n', '<br>')
    output.append('<li>')
    output.append('<div class="problem">%s</div>' %
                  transitfeed.EncodeUnicode(problem_text))
    try:
      if hasattr(e, 'row_num'):
        line_str = 'line %d of ' % e.row_num
      else:
        line_str = ''
      output.append('in %s<code>%s</code><br>\n' %
                    (line_str, e.file_name))
      row = e.row
      headers = e.headers
      column_name = e.column_name
      table_header = ''  # HTML
      table_data = ''  # HTML
      for header, value in zip(headers, row):
        attributes = ''
        if header == column_name:
          attributes = ' class="problem"'
        table_header += '<th%s>%s</th>' % (attributes, header)
        table_data += '<td%s>%s</td>' % (attributes, value)
      # Make sure output is encoded into UTF-8
      output.append('<table class="dump"><tr>%s</tr>\n' %
                    transitfeed.EncodeUnicode(table_header))
      output.append('<tr>%s</tr></table>\n' %
                    transitfeed.EncodeUnicode(table_data))
    except AttributeError, e:
      pass  # Hope this was getting an attribute from e ;-)
    output.append('<br></li>\n')

  def FormatCount(self):
    return ProblemCountText(self.ErrorCount(), self.WarningCount())

  def CountTable(self):
    output = []
    output.append('<table class="count_outside">\n')
    output.append('<tr>')
    if self.ProblemListMap(TYPE_ERROR):
      output.append('<td><span class="fail">%s</span></td>' %
                    PrettyNumberWord(self.ErrorCount(), "error"))
    if self.ProblemListMap(TYPE_WARNING):
      output.append('<td><span class="fail">%s</span></td>' %
                    PrettyNumberWord(self.WarningCount(), "warning"))
    output.append('</tr>\n<tr>')
    if self.ProblemListMap(TYPE_ERROR):
      output.append('<td>\n')
      output.append(self.FormatTypeSummaryTable("Error",
                    self.ProblemListMap(TYPE_ERROR)))
      output.append('</td>\n')
    if self.ProblemListMap(TYPE_WARNING):
      output.append('<td>\n')
      output.append(self.FormatTypeSummaryTable("Warning",
                    self.ProblemListMap(TYPE_WARNING)))
      output.append('</td>\n')
    output.append('</table>')
    return ''.join(output)

  def WriteOutput(self, feed_location, f, schedule, other_problems):
    """Write the html output to f."""
    if self.HasIssues():
      if self.ErrorCount() + self.WarningCount() == 1:
        summary = ('<span class="fail">Found this problem:</span>\n%s' %
                   self.CountTable())
      else:
        summary = ('<span class="fail">Found these problems:</span>\n%s' %
                   self.CountTable())
    else:
      summary = '<span class="pass">feed validated successfully</span>'
    if other_problems is not None:
      summary = ('<span class="fail">\n%s</span><br><br>' %
                 other_problems) + summary

    basename = os.path.basename(feed_location)
    feed_path = (feed_location[:feed_location.rfind(basename)], basename)

    agencies = ', '.join(['<a href="%s">%s</a>' % (a.agency_url, a.agency_name)
                          for a in schedule.GetAgencyList()])
    if not agencies:
      agencies = '?'

    dates = "No valid service dates found"
    (start, end) = schedule.GetDateRange()
    if start and end:
      def FormatDate(yyyymmdd):
        src_format = "%Y%m%d"
        dst_format = "%B %d, %Y"
        try:
          return time.strftime(dst_format,
                               time.strptime(yyyymmdd, src_format))
        except ValueError:
          return yyyymmdd

      formatted_start = FormatDate(start)
      formatted_end = FormatDate(end)
      dates = "%s to %s" % (formatted_start, formatted_end)

    calendar_summary = CalendarSummary(schedule)
    if calendar_summary:
      calendar_summary_html = """<br>
During the upcoming service dates %(date_summary_range)s:
<table>
<tr><th class="header">Average trips per date:</th><td class="header">%(mean_trips)s</td></tr>
<tr><th class="header">Most trips on a date:</th><td class="header">%(max_trips)s, on %(max_trips_dates)s</td></tr>
<tr><th class="header">Least trips on a date:</th><td class="header">%(min_trips)s, on %(min_trips_dates)s</td></tr>
</table>""" % calendar_summary
    else:
      calendar_summary_html = ""

    output_prefix = """
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>FeedValidator: %(feed_file)s</title>
<style>
body {font-family: Georgia, serif; background-color: white}
.path {color: gray}
div.problem {max-width: 500px}
table.dump td,th {background-color: khaki; padding: 2px; font-family:monospace}
table.dump td.problem,th.problem {background-color: dc143c; color: white; padding: 2px; font-family:monospace}
table.count_outside td {vertical-align: top}
table.count_outside {border-spacing: 0px; }
table {border-spacing: 5px 0px; margin-top: 3px}
h3.issueHeader {padding-left: 0.5em}
h4.issueHeader {padding-left: 1em}
.pass {background-color: lightgreen}
.fail {background-color: yellow}
.pass, .fail {font-size: 16pt}
.header {background-color: white; font-family: Georgia, serif; padding: 0px}
th.header {text-align: right; font-weight: normal; color: gray}
.footer {font-size: 10pt}
</style>
</head>
<body>
GTFS validation results for feed:<br>
<code><span class="path">%(feed_dir)s</span><b>%(feed_file)s</b></code>
<br><br>
<table>
<tr><th class="header">Agencies:</th><td class="header">%(agencies)s</td></tr>
<tr><th class="header">Routes:</th><td class="header">%(routes)s</td></tr>
<tr><th class="header">Stops:</th><td class="header">%(stops)s</td></tr>
<tr><th class="header">Trips:</th><td class="header">%(trips)s</td></tr>
<tr><th class="header">Shapes:</th><td class="header">%(shapes)s</td></tr>
<tr><th class="header">Effective:</th><td class="header">%(dates)s</td></tr>
</table>
%(calendar_summary)s
<br>
%(problem_summary)s
<br><br>
""" % { "feed_file": feed_path[1],
        "feed_dir": feed_path[0],
        "agencies": agencies,
        "routes": len(schedule.GetRouteList()),
        "stops": len(schedule.GetStopList()),
        "trips": len(schedule.GetTripList()),
        "shapes": len(schedule.GetShapeList()),
        "dates": dates,
        "problem_summary": summary,
        "calendar_summary": calendar_summary_html}

# In output_suffix string
# time.strftime() returns a regular local time string (not a Unicode one) with
# default system encoding. And decode() will then convert this time string back
# into a Unicode string. We use decode() here because we don't want the operating
# system to do any system encoding (which may cause some problem if the string
# contains some non-English characters) for the string. Therefore we decode it
# back to its original Unicode code print.

    time_unicode = (time.strftime('%B %d, %Y at %I:%M %p %Z').
                    decode(sys.getfilesystemencoding()))
    output_suffix = """
<div class="footer">
Generated by <a href="http://code.google.com/p/googletransitdatafeed/wiki/FeedValidator">
FeedValidator</a> version %s on %s.
</div>
</body>
</html>""" % (transitfeed.__version__, time_unicode)

    f.write(transitfeed.EncodeUnicode(output_prefix))
    if self.ProblemListMap(TYPE_ERROR):
      f.write('<h3 class="issueHeader">Errors:</h3>')
      self.FormatType(f, "Error",
                      self.ProblemListMap(TYPE_ERROR).items())
    if self.ProblemListMap(TYPE_WARNING):
      f.write('<h3 class="issueHeader">Warnings:</h3>')
      self.FormatType(f, "Warning",
                      self.ProblemListMap(TYPE_WARNING).items())
    f.write(transitfeed.EncodeUnicode(output_suffix))


def RunValidationOutputFromOptions(feed, options):
  """Validate feed, output results per options and return an exit code."""
  if options.output.upper() == "CONSOLE":
    return RunValidationOutputToConsole(feed, options)
  else:
    return RunValidationOutputToFilename(feed, options, options.output)


def RunValidationOutputToFilename(feed, options, output_filename):
  """Validate feed, save HTML at output_filename and return an exit code."""
  try:
    output_file = open(output_filename, 'w')
    exit_code = RunValidationOutputToFile(feed, options, output_file)
    output_file.close()
  except IOError, e:
    print 'Error while writing %s: %s' % (output_filename, e)
    output_filename = None
    exit_code = 2

  if options.manual_entry and output_filename:
    webbrowser.open('file://%s' % os.path.abspath(output_filename))

  return exit_code


def RunValidationOutputToFile(feed, options, output_file):
  """Validate feed, write HTML to output_file and return an exit code."""
  problems = HTMLCountingProblemReporter(options.limit_per_type)
  schedule, exit_code, other_problems_string = RunValidation(feed, options,
                                                             problems)
  if isinstance(feed, basestring):
    feed_location = feed
  else:
    feed_location = getattr(feed, 'name', repr(feed))
  problems.WriteOutput(feed_location, output_file, schedule,
                       other_problems_string)
  return exit_code


def RunValidationOutputToConsole(feed, options):
  """Validate feed, print reports and return an exit code."""
  problems = CountingConsoleProblemReporter()
  _, exit_code, _ = RunValidation(feed, options, problems)
  return exit_code


def RunValidation(feed, options, problems):
  """Validate feed, returning the loaded Schedule and exit code.

  Args:
    feed: GTFS file, either path of the file as a string or a file object
    options: options object returned by optparse
    problems: transitfeed.ProblemReporter instance

  Returns:
    a transitfeed.Schedule object, exit code and plain text string of other
    problems
    Exit code is 1 if problems are found and 0 if the Schedule is problem free.
    plain text string is '' if no other problems are found.
  """
  other_problems_string = CheckVersion(latest_version=options.latest_version)
  print 'validating %s' % feed
  loader = transitfeed.Loader(feed, problems=problems, extra_validation=False,
                              memory_db=options.memory_db,
                              check_duplicate_trips=\
                              options.check_duplicate_trips)
  schedule = loader.Load()
  schedule.Validate(service_gap_interval=options.service_gap_interval)
  
  if feed == 'IWantMyvalidation-crash.txt':
    # See test/testfeedvalidator.py
    raise Exception('For testing the feed validator crash handler.')

  if other_problems_string:
    print other_problems_string

  if problems.HasIssues():
    print 'ERROR: %s found' % problems.FormatCount()
    return schedule, 1, other_problems_string
  else:
    print 'feed validated successfully'
    return schedule, 0, other_problems_string


def CheckVersion(latest_version=''):
  """
  Check there is newer version of this project.

  Codes are based on http://www.voidspace.org.uk/python/articles/urllib2.shtml
  Already got permission from the copyright holder.
  """
  current_version = transitfeed.__version__
  if not latest_version:
    timeout = 20
    socket.setdefaulttimeout(timeout)
    request = Request(SVN_TAG_URL)

    try:
      response = urlopen(request)
      content = response.read()
      versions = re.findall(r'>transitfeed-([\d\.]+)\/<\/a>', content)
      latest_version = MaxVersion(versions)

    except HTTPError, e:
      return('The server couldn\'t fulfill the request. Error code: %s.'
             % e.code)
    except URLError, e:
      return('We failed to reach transitfeed server. Reason: %s.' % e.reason)

  if not latest_version:
    return('We had trouble parsing the contents of %s.' % SVN_TAG_URL)

  newest_version = MaxVersion([latest_version, current_version])
  if current_version != newest_version:
    return('A new version %s of transitfeed is available. Please visit '
           'http://code.google.com/p/googletransitdatafeed and download.'
           % newest_version)


def main():
  usage = \
'''%prog [options] [<input GTFS.zip>]

Validates GTFS file (or directory) <input GTFS.zip> and writes a HTML
report of the results to validation-results.html.

If <input GTFS.zip> is ommited the filename is read from the console. Dragging
a file into the console may enter the filename.

For more information see
http://code.google.com/p/googletransitdatafeed/wiki/FeedValidator
'''

  parser = util.OptionParserLongError(
      usage=usage, version='%prog '+transitfeed.__version__)
  parser.add_option('-n', '--noprompt', action='store_false',
                    dest='manual_entry',
                    help='do not prompt for feed location or load output in '
                    'browser')
  parser.add_option('-o', '--output', dest='output', metavar='FILE',
                    help='write html output to FILE or --output=CONSOLE to '
                    'print all errors and warnings to the command console')
  parser.add_option('-p', '--performance', action='store_true',
                    dest='performance',
                    help='output memory and time performance (Availability: '
                    'Unix')
  parser.add_option('-m', '--memory_db', dest='memory_db',  action='store_true',
                    help='Use in-memory sqlite db instead of a temporary file. '
                         'It is faster but uses more RAM.')
  parser.add_option('-d', '--duplicate_trip_check',
                    dest='check_duplicate_trips', action='store_true',
                    help='Check for duplicate trips which go through the same '
                    'stops with same service and start times')
  parser.add_option('-l', '--limit_per_type',
                    dest='limit_per_type', action='store', type='int',
                    help='Maximum number of errors and warnings to keep of '
                    'each type')
  parser.add_option('--latest_version', dest='latest_version',
                    action='store',
                    help='a version number such as 1.2.1 or None to get the '
                    'latest version from code.google.com. Output a warning if '
                    'transitfeed.py is older than this version.')
  parser.add_option('--service_gap_interval', 
                    dest='service_gap_interval',
                    action='store',
                    type='int',
                    help='the number of consecutive days to search for with no '
                    'scheduled service. For each interval with no service '
                    'having this number of days or more a warning will be '
                    'issued')

  parser.set_defaults(manual_entry=True, output='validation-results.html',
                      memory_db=False, check_duplicate_trips=False,
                      limit_per_type=5, latest_version='',
                      service_gap_interval=13)
  (options, args) = parser.parse_args()

  if not len(args) == 1:
    if options.manual_entry:
      feed = raw_input('Enter Feed Location: ')
    else:
      parser.error('You must provide the path of a single feed')
  else:
    feed = args[0]

  feed = feed.strip('"')

  if options.performance:
    return ProfileRunValidationOutputFromOptions(feed, options)
  else:
    return RunValidationOutputFromOptions(feed, options)


def ProfileRunValidationOutputFromOptions(feed, options):
  """Run RunValidationOutputFromOptions, print profile and return exit code."""
  import cProfile
  import pstats
  # runctx will modify a dict, but not locals(). We need a way to get rv back.
  locals_for_exec = locals()
  cProfile.runctx('rv = RunValidationOutputFromOptions(feed, options)',
                  globals(), locals_for_exec, 'validate-stats')

  # Only available on Unix, http://docs.python.org/lib/module-resource.html
  import resource
  print "Time: %d seconds" % (
      resource.getrusage(resource.RUSAGE_SELF).ru_utime +
      resource.getrusage(resource.RUSAGE_SELF).ru_stime)

  # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/286222
  # http://aspn.activestate.com/ASPN/Cookbook/ "The recipes are freely
  # available for review and use."
  def _VmB(VmKey):
    """Return size from proc status in bytes."""
    _proc_status = '/proc/%d/status' % os.getpid()
    _scale = {'kB': 1024.0, 'mB': 1024.0*1024.0,
              'KB': 1024.0, 'MB': 1024.0*1024.0}

     # get pseudo file  /proc/<pid>/status
    try:
        t = open(_proc_status)
        v = t.read()
        t.close()
    except:
        raise Exception("no proc file %s" % _proc_status)
        return 0  # non-Linux?
     # get VmKey line e.g. 'VmRSS:  9999  kB\n ...'
    i = v.index(VmKey)
    v = v[i:].split(None, 3)  # whitespace
    if len(v) < 3:
        raise Exception("%s" % v)
        return 0  # invalid format?
     # convert Vm value to bytes
    return int(float(v[1]) * _scale[v[2]])

  # I ran this on over a hundred GTFS files, comparing VmSize to VmRSS
  # (resident set size). The difference was always under 2% or 3MB.
  print "Virtual Memory Size: %d bytes" % _VmB('VmSize:')

  # Output report of where CPU time was spent.
  p = pstats.Stats('validate-stats')
  p.strip_dirs()
  p.sort_stats('cumulative').print_stats(30)
  p.sort_stats('cumulative').print_callers(30)
  return locals_for_exec['rv']


if __name__ == '__main__':
  util.RunWithCrashHandler(main)
