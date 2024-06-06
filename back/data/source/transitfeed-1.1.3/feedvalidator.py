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

# Validates a Google Transit Feed Specification feed.
#
#
# usage: feedvalidator.py [options] feed_filename
#
# options:
#   --version             show program's version number and exit
#   -h, --help            show this help message and exit
#   -n, --noprompt        do not prompt for feed location or load output in
#                         browser
#   -o FILE, --output=FILE
#                         write html output to FILE

import codecs
import optparse
import os.path
import time
import transitfeed
import sys
import webbrowser

DEFAULT_UNUSED_LIMIT = 5  # number of unused stops to print

def ProblemCountText(error_count, warning_count):
  error_text = ''
  warning_text= ''
  
  if error_count > 1:
    error_text = '%d errors' % error_count
  elif error_count == 1:
    error_text = 'one error'
    
  if warning_count > 1:
    warning_text = '%d warnings' % warning_count
  elif warning_count == 1:
    warning_text = 'one warning'
  
  # Add a way to jump to the warning section when it's useful  
  if error_count and warning_count:
    warning_text = '<a href="#warnings">%s</a>' % warning_text
    
  results = []
  if error_text:
    results.append(error_text)
  if warning_text:
    results.append(warning_text)
    
  return ' and '.join(results)

class HTMLCountingProblemReporter(transitfeed.ProblemReporter):
  def __init__(self):
    transitfeed.ProblemReporter.__init__(self)
    self._error_output = []
    self._warning_output = []
    self.error_count = 0
    self.warning_count = 0
    self.unused_stops = []  # [(stop_id, stop_name)...]

  def HasIssues(self):
    return self.error_count or self.warning_count

  def UnusedStop(self, stop_id, stop_name):
    self.warning_count += 1
    self.unused_stops.append((stop_id, stop_name))

  def _Report(self, e):
    if e.IsWarning():
      self.warning_count += 1
      output = self._warning_output
    else:
      self.error_count += 1
      output = self._error_output
    d = e.GetDict()
    for k in ('file_name', 'feedname', 'column_name'):
      if k in d.keys():
        d[k] = '<code>%s</code>' % d[k]
    problem_text = e.FormatProblem(d).replace('\n', '<br>')
    output.append('<li>')
    output.append('<div class="problem">%s</div>' %
                  transitfeed.EncodeUnicode(problem_text))
    try:
      output.append('in line %d of <code>%s</code><br>\n' %
                    (e.row_num, e.file_name))
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
      output.append('<table><tr>%s</tr>\n' % table_header)
      # Make sure output contains strings with UTF-8 or binary data, not unicode
      output.append('<tr>%s</tr></table>\n' %
                    transitfeed.EncodeUnicode(table_data))
    except AttributeError, e:
      pass  # Hope this was getting an attribute from e ;-)
    output.append('<br></li>\n')

  def _UnusedStopSection(self):
    unused = []
    unused_count = len(self.unused_stops)
    if unused_count:
      if unused_count == 1:
        unused.append('%d.<br>' % self.warning_count)
        unused.append('<div class="unused">')
        unused.append('one stop was found that wasn\'t')
      else:
        unused.append('%d&ndash;%d.<br>' %
                      (self.warning_count - unused_count + 1,
                       self.warning_count))
        unused.append('<div class="unused">')
        unused.append('%d stops were found that weren\'t' % unused_count)
      unused.append(' used in any trips')
      if unused_count > DEFAULT_UNUSED_LIMIT:
        self.unused_stops = self.unused_stops[:DEFAULT_UNUSED_LIMIT]
        unused.append(' (the first %d are shown below)' %
                      len(self.unused_stops))
      unused.append(':<br>')
      unused.append('<table><tr><th>stop_name</th><th>stop_id</th></tr>')
      for stop_id, stop_name in self.unused_stops:
        unused.append('<tr><td>%s</td><td>%s</td></tr>' % (stop_name, stop_id))
      unused.append('</table><br>')
      unused.append('</div>')
    return ''.join(unused)

  def WriteOutput(self, feed_location, f, schedule):
    """Write the html output to f."""
    if problems.HasIssues():
      summary = ('<span class="fail">%s found</span>' %
                 ProblemCountText(problems.error_count, problems.warning_count))
    else:
      summary = '<span class="pass">feed validated successfully</span>'

    basename = os.path.basename(feed_location)
    feed_path = (feed_location[:feed_location.rfind(basename)], basename)

    agencies = ', '.join(['<a href="%s">%s</a>' % (a.agency_url, a.agency_name)
                          for a in schedule.GetAgencyList()])
    if not agencies:
      agencies = '?'

    dates = "No valid service dates found"
    (start, end) = schedule.GetDateRange()
    if start and end:
      src_format = "%Y%m%d"
      dst_format = "%B %d, %Y"
      formatted_start = time.strftime(dst_format,
                                      time.strptime(start, src_format))
      formatted_end = time.strftime(dst_format, time.strptime(end, src_format))
      dates = "%s to %s" % (formatted_start, formatted_end)

    output_prefix = """
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>FeedValidator: %(feed_file)s</title>
<style>
body {font-family: Georgia, serif; background-color: white}
.path {color: gray}
div.problem {max-width: 500px}
td,th {background-color: khaki; padding: 2px; font-family:monospace}
td.problem,th.problem {background-color: dc143c; color: white; padding: 2px; font-family:monospace}
table {border-spacing: 5px 0px; margin-top: 3px}
h3.issueHeader {padding-left: 1em}
span.pass {background-color: lightgreen}
span.fail {background-color: yellow}
.pass, .fail {font-size: 16pt; padding: 3px}
ol,.unused {padding-left: 40pt}
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
<br>
%(summary)s
<br><br>
""" % { "feed_file": feed_path[1],
            "feed_dir": feed_path[0],
            "agencies": agencies,
            "routes": len(schedule.GetRouteList()),
            "stops": len(schedule.GetStopList()),
            "trips": len(schedule.GetTripList()),
            "shapes": len(schedule.GetShapeList()),
            "dates": dates,
            "summary": summary }

    output_suffix = """
%s
<div class="footer">
Generated by <a href="http://code.google.com/p/googletransitdatafeed/wiki/FeedValidator">
FeedValidator</a> version %s on %s.
</div>
</body>
</html>""" % (self._UnusedStopSection(),
              transitfeed.__version__,
              time.strftime('%B %d, %Y at %I:%M %p %Z'))

    f.write(transitfeed.EncodeUnicode(output_prefix))
    if self._error_output:
      f.write('<h3 class="issueHeader">Errors:</h3><ol>')
      f.writelines(self._error_output)
      f.write('</ol>')
    if self._warning_output:
      f.write('<a name="warnings">'
              '<h3 class="issueHeader">Warnings:</h3></a><ol>')
      f.writelines(self._warning_output)
      f.write('</ol>')
    f.write(transitfeed.EncodeUnicode(output_suffix))

if __name__ == '__main__':
  parser = optparse.OptionParser(usage='usage: %prog [options] feed_filename',
                                 version='%prog '+transitfeed.__version__)
  parser.add_option('-n', '--noprompt', action='store_false',
                    dest='manual_entry',
                    help='do not prompt for feed location or load output in browser')
  parser.add_option('-o', '--output', dest='output', metavar='FILE',
                    help='write html output to FILE')
  parser.set_defaults(manual_entry=True, output='validation-results.html')
  (options, args) = parser.parse_args()
  manual_entry = options.manual_entry
  if not len(args) == 1:
    if manual_entry:
      feed = raw_input('Enter Feed Location: ')
    else:
      print >>sys.stderr, parser.format_help()
      print >>sys.stderr, '\n\nYou must provide the path of a single feed\n\n'
      sys.exit(2)
  else:
    feed = args[0]

  feed = feed.strip('"')
  print 'validating %s' % feed
  problems = HTMLCountingProblemReporter()
  loader = transitfeed.Loader(feed, problems=problems, extra_validation=True)
  schedule = loader.Load()

  exit_code = 0
  if problems.HasIssues():
    print 'ERROR: %s found' % ProblemCountText(problems.error_count,
                                               problems.warning_count)
    exit_code = 1
  else:
    print 'feed validated successfully'

  output_filename = options.output
  output_file = open(output_filename, 'w')
  problems.WriteOutput(os.path.abspath(feed), output_file, schedule)
  output_file.close()
  if manual_entry:
    webbrowser.open('file://%s' % os.path.abspath(output_filename))

  sys.exit(exit_code)
