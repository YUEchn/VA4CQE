#!/usr/bin/python2.4

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

# An example application that uses the transitfeed module.
#
# You must provide a Google Maps API key.
#
# Usage:
# schedule_viewer.py --key `cat key` --port 8765 --feed_filename feed.zip

import BaseHTTPServer, sys, urlparse
import bisect
import marey_graph
import mimetypes
from optparse import OptionParser
import os.path
import re
import signal
import simplejson
import time
import transitfeed


# By default Windows kills Python with Ctrl+Break. Instead make Ctrl+Break
# raise a KeyboardInterrupt.
if hasattr(signal, 'SIGBREAK'):
  signal.signal(signal.SIGBREAK, signal.default_int_handler) 


mimetypes.add_type('text/plain', '.vbs')


class ResultEncoder(simplejson.JSONEncoder):
  def default(self, obj):
    try:
      iterable = iter(obj)
    except TypeError:
      pass
    else:
      return list(iterable)
    return simplejson.JSONEncoder.default(self, obj)


class ScheduleRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  def __init__(self, request, client_address, socket_server):
    BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, request, client_address, socket_server)

  def do_GET(self):
    scheme, host, path, x, params, fragment = urlparse.urlparse(self.path)
    parsed_params = {}
    for k in params.split('&'):
      if '=' in k:
        k, v = k.split('=', 1)
        parsed_params[k] = v
      else:
        parsed_params[k] = ''

    if path == '/':
      return self.handle_GET_home()

    m = re.match(r'/json/([a-z]{1,64})', path)
    if m:
      handler_name = 'handle_json_GET_%s' % m.group(1)
      handler = getattr(self, handler_name, None)
      if callable(handler):
        return self.handle_json_wrapper_GET(handler, parsed_params)

    # Restrict allowable file names to prevent relative path attacks etc
    m = re.match(r'/file/([a-z0-9_-]{1,64}\.?[a-z0-9_-]{1,64})$', path)
    if m and m.group(1):
      try:
        f, mime_type = self.OpenFile(m.group(1))
        return self.handle_static_file_GET(f, mime_type)
      except IOError, e:
        print "Error: unable to open %s" % m.group(1)
        # Ignore and treat as 404

    m = re.match(r'/([a-z]{1,64})', path)
    if m:
      handler_name = 'handle_GET_%s' % m.group(1)
      handler = getattr(self, handler_name, None)
      if callable(handler):
        return handler(parsed_params)

    return self.handle_GET_default(parsed_params, path)

  def OpenFile(self, filename):
    """Try to open filename in the static files directory of this server.
    Return a tuple (file object, string mime_type) or raise an exception."""
    (mime_type, encoding) = mimetypes.guess_type(filename)
    assert mime_type
    # A crude guess of when we should use binary mode. Without it non-unix
    # platforms may corrupt binary files.
    if mime_type.startswith('text/'):
      mode = 'r'
    else:
      mode = 'rb'
    return open(os.path.join(self.server.file_dir, filename), mode), mime_type

  def handle_GET_default(self, parsed_params, path):
    self.send_error(404)

  def handle_static_file_GET(self, fh, mime_type):
    content = fh.read()
    self.send_response(200)
    self.send_header('Content-Type', mime_type)
    self.send_header('Content-Length', str(len(content)))
    self.end_headers()
    self.wfile.write(content)

  def handle_GET_home(self):
    schedule = self.server.schedule
    (min_lat, min_lon, max_lat, max_lon) = schedule.GetStopBoundingBox()

    agency = ', '.join(a.agency_name for a in schedule.GetAgencyList()).encode('utf-8')

    key = self.server.key

    # A very simple template system. For a fixed set of values replace [xxx]
    # with the value of local variable xxx
    f, _ = self.OpenFile('index.html')
    content = f.read()
    for v in ('agency', 'min_lat', 'min_lon', 'max_lat', 'max_lon', 'key'):
      content = content.replace('[%s]' % v, str(locals()[v]))

    self.send_response(200)
    self.send_header('Content-Type', 'text/html')
    self.send_header('Content-Length', str(len(content)))
    self.end_headers()
    self.wfile.write(content)

  def handle_json_GET_routepatterns(self, params):
    """Given a route_id generate a list of patterns of the route. For each
    pattern include some basic information and a few sample trips."""
    schedule = self.server.schedule
    route = schedule.GetRoute(params.get('route', None))
    if not route:
      self.send_error(404)
      return
    time = int(params.get('time', 0))
    sample_size = 3  # For each pattern return the start time for this many trips

    pattern_id_trip_dict = route.GetPatternIdTripDict()
    patterns = []

    for pattern_id, trips in pattern_id_trip_dict.items():
      time_stops = trips[0].GetTimeStops()
      if not time_stops:
        continue
      name = u'%s to %s, %d stops' % (time_stops[0][2].stop_name, time_stops[-1][2].stop_name, len(time_stops))
      transitfeed.SortListOfTripByTime(trips)

      num_trips = len(trips)
      if num_trips <= sample_size:
        start_sample_index = 0
        num_after_sample = 0
      else:
        # Will return sample_size trips that start after the 'time' param.

        # Linear search because I couldn't find a built-in way to do a binary
        # search with a custom key.
        start_sample_index = len(trips)
        for i, trip in enumerate(trips):
          if trip.GetStartTime() >= time:
            start_sample_index = i
            break

        num_after_sample = num_trips - (start_sample_index + sample_size)
        if num_after_sample < 0:
          # Less than sample_size trips start after 'time' so return all the
          # last sample_size trips.
          num_after_sample = 0
          start_sample_index = num_trips - sample_size

      sample = []
      for t in trips[start_sample_index:start_sample_index + sample_size]:
        sample.append( (t.GetStartTime(), t.trip_id) )

      patterns.append((name, pattern_id, start_sample_index, sample, num_after_sample))

    patterns.sort()
    return patterns

  def handle_json_wrapper_GET(self, handler, parsed_params):
    """Call handler and output the return value in JSON."""
    result = handler(parsed_params)
    content = ResultEncoder().encode(result)
    self.send_response(200)
    self.send_header('Content-Type', 'text/plain')
    self.send_header('Content-Length', str(len(content)))
    self.end_headers()
    self.wfile.write(content)

  def handle_json_GET_routes(self, params):
    """Return a list of all routes."""
    result = []
    for r in schedule.GetRouteList():
      result.append( (r.route_id, r.route_short_name, r.route_long_name) )
    result.sort(key = lambda x: x[1:3])
    return result

  def handle_json_GET_routerow(self, params):
    route = schedule.GetRoute(params.get('route', None))
    return [transitfeed.Route._FIELD_NAMES, route.GetFieldValuesTuple()]

  def handle_json_GET_triprows(self, params):
    """Return a list of rows from the feed file that are related to this
    trip."""
    trip = schedule.GetTrip(params.get('trip', None))
    route = schedule.GetRoute(trip.route_id)
    trip_row = {}
    for column in transitfeed.Trip._FIELD_NAMES:
      if getattr(trip, column) != None:
        trip_row[column] = getattr(trip, column)
    route_row = {}
    for column in transitfeed.Route._FIELD_NAMES:
      if getattr(route, column) != None:
        route_row[column] = getattr(route, column)
    return [['trips.txt', trip_row], ['routes.txt', route_row]]

  def handle_json_GET_tripstoptimes(self, params):
    schedule = self.server.schedule
    trip = schedule.GetTrip(params.get('trip'))
    time_stops = trip.GetTimeStops()
    stops = []
    times = []
    for arr,dep,stop in time_stops:
      stops.append(stop.GetFieldValuesTuple())
      times.append(arr)
    return [stops, times]

  def handle_json_GET_tripshape(self, params):
    schedule = self.server.schedule
    trip = schedule.GetTrip(params.get('trip'))
    # TODO: support for shape.txt and part of a trip
    time_stops = trip.GetTimeStops()
    points = []
    for arr,dep,stop in time_stops:
      points.append((stop.stop_lat, stop.stop_lon))
    return points

  def handle_json_GET_neareststops(self, params):
    """Return a list of the nearest 'limit' stops to 'lat', 'lon'"""
    schedule = self.server.schedule
    lat = float(params.get('lat'))
    lon = float(params.get('lon'))
    limit = int(params.get('limit'))
    stops = schedule.GetNearestStops(lat=lat, lon=lon, n=limit)
    return [s.GetFieldValuesTuple() for s in stops]

  def handle_json_GET_boundboxstops(self, params):
    """Return a list of up to 'limit' stops within bounding box with 'n','e'
    and 's','w' in the NE and SW corners. Does not handle boxes crossing
    longitude line 180."""
    schedule = self.server.schedule
    n = float(params.get('n'))
    e = float(params.get('e'))
    s = float(params.get('s'))
    w = float(params.get('w'))
    limit = int(params.get('limit'))
    stops = schedule.GetStopsInBoundingBox(north=n, east=e, south=s, west=w, n=limit)
    return [s.GetFieldValuesTuple() for s in stops]

  def handle_json_GET_stopsearch(self, params):
    schedule = self.server.schedule
    query = params.get('q', None)
    matches = []
    for s in schedule.GetStopList():
      if s.stop_id.lower().find(query) != -1 or s.stop_name.lower().find(query) != -1:
        matches.append(s.GetFieldValuesTuple())
    return matches

  def handle_json_GET_stoptrips(self, params):
    """Given a stop_id and time in seconds since midnight return the next
    trips to visit the stop."""
    schedule = self.server.schedule
    stop = schedule.GetStop(params.get('stop', None))
    time = int(params.get('time', 0))
    time_trips = stop.GetStopTimeTrips()
    time_trips.sort()  # OPT: use bisect.insort to make this O(N*ln(N)) -> O(N)
    # Keep the first 5 after param 'time'.
    # Need make a tuple to find correct bisect point
    time_trips = time_trips[bisect.bisect_left(time_trips, (time, 0)):]
    time_trips = time_trips[:5]
    # TODO: combine times for a route to show next 2 departure times
    return [(time, trip.GetFieldValuesTuple()) for time, trip in time_trips]

  def handle_GET_ttablegraph(self,params):
    """Draw a Marey graph in SVG for a pattern (collection of trips in a route
    that visit the same sequence of stops)."""
    schedule = self.server.schedule
    marey = marey_graph.MareyGraph()
    trip = schedule.GetTrip(params.get('trip', None))
    route = schedule.GetRoute(trip.route_id)
    height = int(params.get('height', 300))

    if not route:
      print 'no such route'
      self.send_error(404)
      return

    pattern_id_trip_dict = route.GetPatternIdTripDict()
    pattern_id = trip.pattern_id
    if pattern_id not in pattern_id_trip_dict:
      print 'no pattern %s found in %s' % (pattern_id, pattern_id_trip_dict.keys())
      self.send_error(404)
      return
    triplist = pattern_id_trip_dict[pattern_id]

    pattern_start_time = min((t.GetStartTime() for t in triplist))
    pattern_end_time = max((t.GetEndTime() for t in triplist))

    marey.SetSpan(pattern_start_time,pattern_end_time)
    marey.Draw(triplist[0].GetPattern(), triplist, height)

    content = marey.Draw()

    self.send_response(200)
    self.send_header('Content-Type', 'image/svg+xml')
    self.send_header('Content-Length', str(len(content)))
    self.end_headers()
    self.wfile.write(content)


def StartServerThread(server):
  """Start server in its own thread because KeyboardInterrupt doesn't
  interrupt a socket call in Windows."""
  # Code taken from
  # http://mail.python.org/pipermail/python-list/2003-July/212751.html
  # An alternate approach is shown at
  # http://groups.google.com/group/webpy/msg/9f41fd8430c188dc
  import threading
  th = threading.Thread(target=lambda: server.serve_forever())
  th.setDaemon(1)
  th.start()
  # I don't care about shutting down the server thread cleanly. If you kill
  # python while it is serving a request the browser may get an incomplete
  # reply.


if __name__ == '__main__':
  parser = OptionParser()
  parser.add_option('--feed_filename', dest='feed_filename',
                    help='file name of feed to load')
  parser.add_option('--key', dest='key',
                    help='Google Maps API key')
  parser.add_option('--port', dest='port', type='int',
                    help='port on which to listen')
  parser.add_option('--file_dir', dest='file_dir',
                    help='directory containing static files')
  parser.set_defaults(port=8765, file_dir='schedule_viewer_files')
  (options, args) = parser.parse_args()

  schedule = transitfeed.Schedule(problem_reporter=transitfeed.ProblemReporter())
  print 'Loading data from feed "%s"...' % options.feed_filename
  print '(this may take a few minutes for larger cities)'
  schedule.Load(options.feed_filename)

  server = BaseHTTPServer.HTTPServer(server_address=('', options.port),
                                     RequestHandlerClass=ScheduleRequestHandler)
  server.key = options.key
  server.schedule = schedule
  server.file_dir = options.file_dir

  StartServerThread(server)  # Spawns a thread for server and returns
  print "To view, point your browser at http://%s:%d/" \
    % (server.server_name, server.server_port)

  try:
    while 1:
      time.sleep(0.5)
  except KeyboardInterrupt:
    pass
