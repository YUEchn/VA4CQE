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

# Unit tests for the transitfeed module.

import dircache
import os.path
import sys
import tempfile
import transitfeed
import unittest
import StringIO


def DataPath(path):
  here = os.path.dirname(__file__)
  return os.path.join(here, 'data', path)

def GetDataPathContents():
  here = os.path.dirname(__file__)
  return dircache.listdir(os.path.join(here, 'data'))


class TestFailureProblemReporter(transitfeed.ProblemReporter):
  """Causes a test failure immediately on any problem."""
  def __init__(self, test_case):
    transitfeed.ProblemReporter.__init__(self)
    self.test_case = test_case

  def _Report(self, problem_text):
    self.test_case.fail(problem_text)


class RedirectStdOutTestCaseBase(unittest.TestCase):
  """Save stdout to the StringIO buffer self.this_stdout"""
  def setUp(self):
    self.saved_stdout = sys.stdout
    self.this_stdout = StringIO.StringIO()
    sys.stdout = self.this_stdout

  def tearDown(self):
    sys.stdout = self.saved_stdout
    self.this_stdout.close()


# ensure that there are no exceptions when attempting to load
# (so that the validator won't crash)
class NoExceptionTestCase(RedirectStdOutTestCaseBase):
  def runTest(self):
    for feed in GetDataPathContents():
      loader = transitfeed.Loader(DataPath(feed),
                                  problems=transitfeed.ProblemReporter(),
                                  extra_validation=True)
      schedule = loader.Load()
      schedule.Validate()


class LoadTestCase(unittest.TestCase):
  problems = transitfeed.ExceptionProblemReporter()

  def ExpectInvalidValue(self, feed_name, field_name):
    loader = transitfeed.Loader(
      DataPath(feed_name), problems=self.problems, extra_validation=True)
    try:
      loader.Load()
      self.fail('InvalidValue exception expected')
    except transitfeed.InvalidValue, e:
      self.assertEqual(field_name, e.field_name)

  def ExpectMissingFile(self, feed_name, file_name):
    loader = transitfeed.Loader(
      DataPath(feed_name), problems=self.problems, extra_validation=True)
    try:
      loader.Load()
      self.fail('MissingFile exception expected')
    except transitfeed.MissingFile, e:
      self.assertEqual(file_name, e.file_name)


class LoadFromZipTestCase(unittest.TestCase):
  def runTest(self):
    loader = transitfeed.Loader(
      DataPath('good_feed.zip'),
      problems = TestFailureProblemReporter(self),
      extra_validation = True)
    loader.Load()

    # now try using Schedule.Load
    schedule = transitfeed.Schedule(
        problem_reporter=transitfeed.ExceptionProblemReporter())
    schedule.Load(DataPath('good_feed.zip'), extra_validation=True)


class LoadAndRewriteFromZipTestCase(unittest.TestCase):
  def runTest(self):
    schedule = transitfeed.Schedule(
        problem_reporter=transitfeed.ExceptionProblemReporter())
    schedule.Load(DataPath('good_feed.zip'), extra_validation=True)

    # Finally see if write crashes
    schedule.WriteGoogleTransitFeed(tempfile.TemporaryFile())


class LoadFromDirectoryTestCase(unittest.TestCase):
  def runTest(self):
    loader = transitfeed.Loader(
      DataPath('good_feed'),
      problems = TestFailureProblemReporter(self),
      extra_validation = True)
    loader.Load()


class LoadUnknownFeedTestCase(unittest.TestCase):
  def runTest(self):
    feed_name = DataPath('unknown_feed')
    loader = transitfeed.Loader(
      feed_name,
      problems = transitfeed.ExceptionProblemReporter(),
      extra_validation = True)
    try:
      loader.Load()
      self.fail('FeedNotFound exception expected')
    except transitfeed.FeedNotFound, e:
      self.assertEqual(feed_name, e.feed_name)

class LoadUnknownFormatTestCase(unittest.TestCase):
  def runTest(self):
    feed_name = DataPath('unknown_format.zip')
    loader = transitfeed.Loader(
      feed_name,
      problems = transitfeed.ExceptionProblemReporter(),
      extra_validation = True)
    try:
      loader.Load()
      self.fail('UnknownFormat exception expected')
    except transitfeed.UnknownFormat, e:
      self.assertEqual(feed_name, e.feed_name)


class LoadExtraCellValidationTestCase(unittest.TestCase):
  """Checks to see that the validation detects too many cells in a row."""
  def runTest(self):
    feed_name = DataPath('extra_row_cells')
    loader = transitfeed.Loader(
      feed_name,
      problems = transitfeed.ExceptionProblemReporter(),
      extra_validation = True)
    try:
      loader.Load()
      self.fail('OtherProblem exception expected')
    except transitfeed.OtherProblem:
      pass


class LoadUTF8BOMTestCase(unittest.TestCase):
  def runTest(self):
    loader = transitfeed.Loader(
      DataPath('utf8bom'),
      problems = TestFailureProblemReporter(self),
      extra_validation = True)
    loader.Load()


class ProblemReporterTestCase(RedirectStdOutTestCaseBase):
  # Unittest for problem reporter
  def testContextWithBadUnicode(self):
    pr = transitfeed.ProblemReporter()
    pr.SetFileContext('filename.foo', 23,
                      [u'Andr\202', u'Person \xec\x9c\xa0 foo', None],
                      [u'1\202', u'2\202', u'3\202'])
    pr._Report('test string')
    pr._Report('\xff\xfe\x80\x88')
    pr._Report(u'\xff\xfe\x80\x88')

  def testNoContextWithBadUnicode(self):
    pr = transitfeed.ProblemReporter()
    pr._Report('test string')
    pr._Report('\xff\xfe\x80\x88')
    pr._Report(u'\xff\xfe\x80\x88')

  def testLongWord(self):
    # Make sure LineWrap doesn't puke
    pr = transitfeed.ProblemReporter()
    pr._Report('nthountheontuhoenuthoentuhntoehuontehuntoehuntoehuntohuntoheuntheounthoeunthoeunthoeuntheontuheontuhoue')



class BadProblemReporterTestCase(RedirectStdOutTestCaseBase):
  """Make sure ProblemReporter doesn't crash when given bad unicode data and
  does find some error"""
  # tom.brown.code-utf8_weaknesses fixed a bug with problem reporter and bad
  # utf-8 strings
  def runTest(self):
    loader = transitfeed.Loader(
      DataPath('bad_utf8'),
      problems = transitfeed.ProblemReporter(),
      extra_validation = True)
    loader.Load()
    self.this_stdout.getvalue().index('Invalid value')  # raises exception if not found


class BadUtf8TestCase(LoadTestCase):
  def runTest(self):
    self.ExpectInvalidValue('bad_utf8', 'agency_name')


class LoadMissingAgencyTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectMissingFile('missing_agency', 'agency.txt')


class LoadMissingStopsTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectMissingFile('missing_stops', 'stops.txt')


class LoadMissingRoutesTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectMissingFile('missing_routes', 'routes.txt')


class LoadMissingTripsTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectMissingFile('missing_trips', 'trips.txt')


class LoadMissingStopTimesTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectMissingFile('missing_stop_times', 'stop_times.txt')


class LoadMissingCalendarTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectMissingFile('missing_calendar', 'calendar.txt')


class EmptyFileTestCase(unittest.TestCase):
  def runTest(self):
    loader = transitfeed.Loader(
      DataPath('empty_file'),
      problems = transitfeed.ExceptionProblemReporter(),
      extra_validation = True)
    try:
      loader.Load()
      self.fail('EmptyFile exception expected')
    except transitfeed.EmptyFile, e:
      self.assertEqual('agency.txt', e.file_name)


class MissingColumnTestCase(unittest.TestCase):
  def runTest(self):
    loader = transitfeed.Loader(
      DataPath('missing_column'),
      problems = transitfeed.ExceptionProblemReporter(),
      extra_validation = True)
    try:
      loader.Load()
      self.fail('MissingColumn exception expected')
    except transitfeed.MissingColumn, e:
      self.assertEqual('agency.txt', e.file_name)
      self.assertEqual('agency_name', e.column_name)


class ZeroBasedStopSequenceTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectInvalidValue('zero_based_stop_sequence', 'stop_sequence')
    
    


class DuplicateStopTestCase(unittest.TestCase):
  def runTest(self):
    schedule = transitfeed.Schedule(
        problem_reporter=transitfeed.ExceptionProblemReporter())
    try:
      schedule.Load(DataPath('duplicate_stop'), extra_validation=True)
      self.fail('OtherProblem exception expected')
    except transitfeed.OtherProblem:
      pass


INVALID_VALUE = Exception()
class ValidationTestCase(unittest.TestCase):
  problems = transitfeed.ExceptionProblemReporter()

  def ExpectMissingValue(self, object, field_name):
    try:
      object.Validate(self.problems)
      self.fail('MissingValue exception expected')
    except transitfeed.MissingValue, e:
      self.assertEqual(field_name, e.field_name)

  def ExpectInvalidValue(self, object, field_name, value=INVALID_VALUE):
    if value==INVALID_VALUE:
      value = object.__getattribute__(field_name)
    self.ExpectInvalidValueException(field_name, value, object.Validate, self.problems)

  def ExpectInvalidValueException(self, field_name, value, f, *args, **kwargs):
    try:
      f(*args, **kwargs)
      self.fail('InvalidValue exception expected')
    except transitfeed.InvalidValue, e:
      self.assertEqual(field_name, e.field_name)
      self.assertEqual(value, e.value)

  def ExpectOtherProblem(self, object):
    try:
      object.Validate(self.problems)
      self.fail('OtherProblem exception expected')
    except transitfeed.OtherProblem:
      pass


class AgencyValidationTestCase(ValidationTestCase):
  def runTest(self):
    # success case
    agency = transitfeed.Agency(name='Test Agency', url='http://example.com',
                                timezone='America/Los_Angeles', id='TA')
    agency.Validate(self.problems)

    # bad agency
    agency = transitfeed.Agency(name='   ', url='http://example.com',
                                timezone='America/Los_Angeles', id='TA')
    self.ExpectMissingValue(agency, 'agency_name')

    # missing url
    agency = transitfeed.Agency(name='Test Agency',
                                timezone='America/Los_Angeles', id='TA')
    self.ExpectMissingValue(agency, 'agency_url')

    # bad url
    agency = transitfeed.Agency(name='Test Agency', url='www.example.com',
                                timezone='America/Los_Angeles', id='TA')
    self.ExpectInvalidValue(agency, 'agency_url')

    # bad time zone
    agency = transitfeed.Agency(name='Test Agency', url='http://example.com',
                                timezone='America/Alviso', id='TA')
    self.ExpectInvalidValue(agency, 'agency_timezone')


class StopValidationTestCase(ValidationTestCase):
  def runTest(self):
    # success case
    stop = transitfeed.Stop()
    stop.stop_id = '45'
    stop.stop_name = 'Couch AT End Table'
    stop.stop_lat = 50.0
    stop.stop_lon = 50.0
    stop.stop_desc = 'Edge of the Couch'
    stop.zone_id = 'A'
    stop.stop_url = 'http://example.com'
    stop.Validate(self.problems)

    # latitute too large
    stop.stop_lat = 100.0
    self.ExpectInvalidValue(stop, 'stop_lat')
    stop.stop_lat = 50.0

    # longitude too large
    stop.stop_lon = 200.0
    self.ExpectInvalidValue(stop, 'stop_lon')
    stop.stop_lon = 50.0

    # lat, lon too close to 0, 0
    stop.stop_lat = 0.0
    stop.stop_lon = 0.0
    self.ExpectInvalidValue(stop, 'stop_lat')
    stop.stop_lat = 50.0
    stop.stop_lon = 50.0

    # invalid stop_url
    stop.stop_url = 'www.example.com'
    self.ExpectInvalidValue(stop, 'stop_url')
    stop.stop_url = 'http://example.com'

    stop.stop_id = '   '
    self.ExpectMissingValue(stop, 'stop_id')
    stop.stop_id = '45'

    stop.stop_name = None
    self.ExpectMissingValue(stop, 'stop_name')
    stop.stop_name = 'Couch AT End Table'

    # description same as name
    stop.stop_desc = 'Couch AT End Table'
    self.ExpectInvalidValue(stop, 'stop_desc')
    stop.stop_desc = 'Edge of the Couch'


class StopTimeValidationTestCase(ValidationTestCase):
  def runTest(self):
    stop = transitfeed.Stop()
    self.ExpectInvalidValueException('arrival_time', '1a:00:00',
        transitfeed.StopTime, self.problems, stop, arrival_time="1a:00:00")
    self.ExpectInvalidValueException('departure_time', '1a:00:00',
        transitfeed.StopTime, self.problems, stop, arrival_time="10:00:00",
        departure_time='1a:00:00')
    self.ExpectInvalidValueException('pickup_type', '7.8',
        transitfeed.StopTime, self.problems, stop, arrival_time="10:00:00",
        departure_time='10:05:00', pickup_type='7.8', drop_off_type='0')
    self.ExpectInvalidValueException('drop_off_type', 'a',
        transitfeed.StopTime, self.problems, stop, arrival_time="10:00:00",
        departure_time='10:05:00', pickup_type='3', drop_off_type='a')
    self.ExpectInvalidValueException('shape_dist_traveled', '$',
        transitfeed.StopTime, self.problems, stop, arrival_time="10:00:00",
        departure_time='10:05:00', pickup_type='3', drop_off_type='0',
        shape_dist_traveled='$')


class RouteValidationTestCase(ValidationTestCase):
  def runTest(self):
    # success case
    route = transitfeed.Route()
    route.route_id = '054C'
    route.route_short_name = '54C'
    route.route_long_name = 'South Side - North Side'
    route.route_type = 7
    route.Validate(self.problems)

    # blank short & long names
    route.route_short_name = ''
    route.route_long_name = '    '
    self.ExpectInvalidValue(route, 'route_short_name')
    route.route_short_name = '54C'
    route.route_long_name = 'South Side - North Side'
    
    # short name too long
    route.route_short_name = 'South Side'
    self.ExpectInvalidValue(route, 'route_short_name')
    route.route_short_name = 'M7bis'  # 5 is OK
    route.Validate(self.problems)
    route.route_short_name = '54C'

    # long name contains short name
    route.route_long_name = '54C South Side - North Side'
    self.ExpectInvalidValue(route, 'route_long_name')
    route.route_long_name = '54C-South Side - North Side'
    self.ExpectInvalidValue(route, 'route_long_name')
    route.route_long_name = 'South Side - North Side'

    # long name is same as short name
    route.route_long_name = '54C'
    self.ExpectInvalidValue(route, 'route_long_name')
    route.route_long_name = 'South Side - North Side'

    # route description is same as short name
    route.route_desc = '54C'
    self.ExpectInvalidValue(route, 'route_desc')
    route.route_desc = None

    # route description is same as long name
    route.route_desc = 'South Side - North Side'
    self.ExpectInvalidValue(route, 'route_desc')
    route.route_desc = None

    # invalid route types
    route.route_type = 8
    self.ExpectInvalidValue(route, 'route_type')
    route.route_type = -1
    self.ExpectInvalidValue(route, 'route_type')
    route.route_type = 7

    # invalid route URL
    route.route_url = 'www.example.com'
    self.ExpectInvalidValue(route, 'route_url')
    route.route_url = None

    # invalid route color
    route.route_color = 'orange'
    self.ExpectInvalidValue(route, 'route_color')
    route.route_color = None

    # invalid route text color
    route.route_text_color = 'orange'
    self.ExpectInvalidValue(route, 'route_text_color')
    route.route_text_color = None

    # missing route ID
    route.route_id = None
    self.ExpectMissingValue(route, 'route_id')
    route.route_id = '054C'


class ShapeValidationTestCase(ValidationTestCase):
  def ExpectFailedAdd(self, shape, lat, lon, dist, field_name, value):
    try:
      shape.AddPoint(lat, lon, dist, self.problems)
      self.fail('Expected validation exception!')
    except transitfeed.InvalidValue, e:
      self.assertEqual(field_name, e.field_name)
      self.assertEqual(value, e.value)

  def runTest(self):
    shape = transitfeed.Shape('TEST')
    self.ExpectOtherProblem(shape)  # no points!

    self.ExpectFailedAdd(shape, 36.905019, -116.763207, -1,
                         'shape_dist_traveled', -1)

    shape.AddPoint(36.915760, -116.751709, 0, self.problems)
    shape.AddPoint(36.905018, -116.763206, 5, self.problems)
    shape.Validate(self.problems)

    shape.shape_id = None
    self.ExpectMissingValue(shape, 'shape_id')
    shape.shape_id = 'TEST'

    self.ExpectFailedAdd(shape, 91, -116.751709, 6, 'shape_pt_lat', 91)
    self.ExpectFailedAdd(shape, -91, -116.751709, 6, 'shape_pt_lat', -91)

    self.ExpectFailedAdd(shape, 36.915760, -181, 6, 'shape_pt_lon', -181)
    self.ExpectFailedAdd(shape, 36.915760, 181, 6, 'shape_pt_lon', 181)

    self.ExpectFailedAdd(shape, 0.5, -0.5, 6, 'shape_pt_lat', 0.5)
    self.ExpectFailedAdd(shape, 0, 0, 6, 'shape_pt_lat', 0)

    # distance decreasing is bad, but staying the same is OK
    self.ExpectFailedAdd(shape, 36.905019, -116.763206, 4,
                         'shape_dist_traveled', 4)
    shape.AddPoint(36.905019, -116.763206, 5, self.problems)

class FareValidationTestCase(ValidationTestCase):
  def runTest(self):
    fare = transitfeed.Fare()
    fare.fare_id = "normal"
    fare.price = 1.50
    fare.currency_type = "USD"
    fare.payment_method = 0
    fare.transfers = 1
    fare.transfer_duration = 7200
    fare.Validate(self.problems)

    fare.fare_id = None
    self.ExpectMissingValue(fare, "fare_id")
    fare.fare_id = ''
    self.ExpectMissingValue(fare, "fare_id")
    fare.fare_id = "normal"

    fare.price = "1.50"
    self.ExpectInvalidValue(fare, "price")
    fare.price = 1
    fare.Validate(self.problems)
    fare.price = None
    self.ExpectMissingValue(fare, "price")
    fare.price = 0.0
    fare.Validate(self.problems)
    fare.price = -1.50
    self.ExpectInvalidValue(fare, "price")
    fare.price = 1.50

    fare.currency_type = ""
    self.ExpectMissingValue(fare, "currency_type")
    fare.currency_type = None
    self.ExpectMissingValue(fare, "currency_type")
    fare.currency_type = "usd"
    self.ExpectInvalidValue(fare, "currency_type")
    fare.currency_type = "KML"
    self.ExpectInvalidValue(fare, "currency_type")
    fare.currency_type = "USD"

    fare.payment_method = "0"
    self.ExpectInvalidValue(fare, "payment_method")
    fare.payment_method = -1
    self.ExpectInvalidValue(fare, "payment_method")
    fare.payment_method = 1
    fare.Validate(self.problems)
    fare.payment_method = 2
    self.ExpectInvalidValue(fare, "payment_method")
    fare.payment_method = None
    self.ExpectMissingValue(fare, "payment_method")
    fare.payment_method = ""
    self.ExpectMissingValue(fare, "payment_method")
    fare.payment_method = 0

    fare.transfers = "1"
    self.ExpectInvalidValue(fare, "transfers")
    fare.transfers = -1
    self.ExpectInvalidValue(fare, "transfers")
    fare.transfers = 2
    fare.Validate(self.problems)
    fare.transfers = 3
    self.ExpectInvalidValue(fare, "transfers")
    fare.transfers = None
    fare.Validate(self.problems)
    fare.transfers = 1

    fare.transfer_duration = 0
    fare.Validate(self.problems)
    fare.transfer_duration = None
    fare.Validate(self.problems)
    fare.transfer_duration = -3600
    self.ExpectInvalidValue(fare, "transfer_duration")
    fare.transfers = 0  # no transfers allowed but duration specified!
    fare.transfer_duration = 3600
    self.ExpectInvalidValue(fare, "transfer_duration")
    fare.transfers = 1
    fare.transfer_duration = "3600"
    self.ExpectInvalidValue(fare, "transfer_duration")
    fare.transfer_duration = 7200


class ServicePeriodValidationTestCase(ValidationTestCase):
  def runTest(self):
    # success case
    period = transitfeed.ServicePeriod()
    period.service_id = 'WEEKDAY'
    period.start_date = '20070101'
    period.end_date = '20071231'
    period.day_of_week[0] = True
    period.Validate(self.problems)

    # missing start_date
    period.start_date = None
    self.ExpectMissingValue(period, 'start_date')
    period.start_date = '20070101'

    # missing end_date
    period.end_date = None
    self.ExpectMissingValue(period, 'end_date')
    period.end_date = '20071231'

    # invalid start_date
    period.start_date = '2007-01-01'
    self.ExpectInvalidValue(period, 'start_date')
    period.start_date = '20070101'

    # invalid end_date
    period.end_date = '2007/12/31'
    self.ExpectInvalidValue(period, 'end_date')
    period.end_date = '20071231'

    # start & end dates out of order
    period.end_date = '20060101'
    self.ExpectInvalidValue(period, 'end_date')
    period.end_date = '20071231'

    # no service in period
    period.day_of_week[0] = False
    self.ExpectOtherProblem(period)
    period.day_of_week[0] = True

    # invalid exception date
    period.SetDateHasService('2007', False)
    self.ExpectInvalidValue(period, 'date', '2007')
    period.ResetDateToNormalService('2007')


class TripValidationTestCase(ValidationTestCase):
  def runTest(self):
    trip = transitfeed.Trip()
    trip.route_id = '054C'
    trip.service_id = 'WEEK'
    trip.trip_id = '054C-00'
    trip.trip_headsign = 'via Polish Hill'
    trip.direction_id = '0'
    trip.block_id = None
    trip.shape_id = None
    trip.Validate(self.problems)

    # missing route ID
    trip.route_id = None
    self.ExpectMissingValue(trip, 'route_id')
    trip.route_id = '054C'

    # missing service ID
    trip.service_id = None
    self.ExpectMissingValue(trip, 'service_id')
    trip.service_id = 'WEEK'

    # missing trip ID
    trip.trip_id = None
    self.ExpectMissingValue(trip, 'trip_id')
    trip.trip_id = '054C-00'

    # invalid direction ID
    trip.direction_id = 'NORTH'
    self.ExpectInvalidValue(trip, 'direction_id')
    trip.direction_id = '0'

    # expect no problems for non-overlapping periods
    trip.AddHeadwayPeriod("06:00:00", "12:00:00", 600)
    trip.AddHeadwayPeriod("01:00:00", "02:00:00", 1200)
    trip.AddHeadwayPeriod("04:00:00", "05:00:00", 1000)
    trip.AddHeadwayPeriod("12:00:00", "19:00:00", 700)
    trip.Validate(self.problems)
    trip.ClearHeadwayPeriods()

    # overlapping headway periods
    trip.AddHeadwayPeriod("00:00:00", "12:00:00", 600)
    trip.AddHeadwayPeriod("06:00:00", "18:00:00", 1200)
    self.ExpectOtherProblem(trip)
    trip.ClearHeadwayPeriods()
    trip.AddHeadwayPeriod("12:00:00", "20:00:00", 600)
    trip.AddHeadwayPeriod("06:00:00", "18:00:00", 1200)
    self.ExpectOtherProblem(trip)
    trip.ClearHeadwayPeriods()
    trip.AddHeadwayPeriod("06:00:00", "12:00:00", 600)
    trip.AddHeadwayPeriod("00:00:00", "25:00:00", 1200)
    self.ExpectOtherProblem(trip)
    trip.ClearHeadwayPeriods()
    trip.AddHeadwayPeriod("00:00:00", "20:00:00", 600)
    trip.AddHeadwayPeriod("06:00:00", "18:00:00", 1200)
    self.ExpectOtherProblem(trip)
    trip.ClearHeadwayPeriods()

    
class TripServiceIDValidationTestCase(ValidationTestCase):
  def runTest(self):
    schedule = transitfeed.Schedule(self.problems)
    schedule.AddAgency("Test Agency", "http://example.com",
                       "America/Los_Angeles")
    service_period = transitfeed.ServicePeriod("WEEK")
    service_period.SetStartDate("20070101")
    service_period.SetEndDate("20071231")
    service_period.SetWeekdayService(True)
    schedule.AddServicePeriodObject(service_period)
    
    schedule.AddRouteObject(
        transitfeed.Route("54C", "Polish Hill", 3, "054C"))

    trip1 = transitfeed.Trip()
    trip1.route_id = "054C"
    trip1.service_id = "WEEKDAY"
    trip1.trip_id = "054C_WEEK"
    try:
      schedule.AddTripObject(trip1)
      self.fail("Expected an InvalidValue for the service_id")
    except transitfeed.InvalidValue, e:
      self.assertEqual("service_id", e.field_name)
      self.assertEqual("WEEKDAY", e.value)
    

class TripHasStopTimeValidationTestCase(ValidationTestCase):
  def runTest(self):
    schedule = transitfeed.Schedule(self.problems)
    schedule.AddAgency("Test Agency", "http://example.com",
                       "America/Los_Angeles")
    schedule.AddRouteObject(
        transitfeed.Route("54C", "Polish Hill", 3, "054C"))

    service_period = transitfeed.ServicePeriod("WEEK")
    service_period.SetStartDate("20070101")
    service_period.SetEndDate("20071231")
    service_period.SetWeekdayService(True)
    schedule.AddServicePeriodObject(service_period)

    trip = transitfeed.Trip()
    trip.route_id = '054C'
    trip.service_id = 'WEEK'
    trip.trip_id = '054C-00'
    trip.trip_headsign = 'via Polish Hill'
    trip.direction_id = '0'
    trip.block_id = None
    trip.shape_id = None
    schedule.AddTripObject(trip)

    # We should get an OtherProblem here because the trip has no stops.
    self.ExpectOtherProblem(schedule)

    # Add a stop, but with only one stop passengers have nowhere to exit!
    stop = transitfeed.Stop(36.425288, -117.133162, "Demo Stop 1", "STOP1")
    schedule.AddStopObject(stop)
    trip.AddStopTime(stop, arrival_time="5:11:00", departure_time="5:12:00")
    self.ExpectOtherProblem(schedule)

    # Add another stop, and then validation should be happy.
    stop = transitfeed.Stop(36.424288, -117.133142, "Demo Stop 2", "STOP2")
    schedule.AddStopObject(stop)
    trip.AddStopTime(stop, arrival_time="5:15:00", departure_time="5:16:00")
    schedule.Validate(self.problems)

    trip.AddStopTime(stop, arrival_secs=None, departure_time="05:20:00")
    trip.AddStopTime(stop, arrival_time="05:22:00", departure_secs=None)

    # Last stop must always have a time
    trip.AddStopTime(stop, arrival_secs=None, departure_secs=None)
    try:
      trip.GetEndTime()
      self.fail('exception expected')
    except transitfeed.Error, e:
      pass


class TripAddStopTimeObjectTestCase(ValidationTestCase):
  def runTest(self):
    schedule = transitfeed.Schedule(problem_reporter=self.problems)
    schedule.AddAgency("\xc8\x8b Fly Agency", "http://iflyagency.com",
                       "America/Los_Angeles")
    service_period = schedule.GetDefaultServicePeriod().SetDateHasService('20070101')
    stop1 = schedule.AddStop(lng=140, lat=48.2, name="Stop 1")
    stop2 = schedule.AddStop(lng=140.001, lat=48.201, name="Stop 2")
    route = schedule.AddRoute("B", "Beta", "Bus")
    trip = route.AddTrip(schedule, "bus trip")
    trip.AddStopTimeObject(transitfeed.StopTime(self.problems, stop1, arrival_secs=10), problems=self.problems)
    trip.AddStopTimeObject(transitfeed.StopTime(self.problems, stop2, arrival_secs=20), problems=self.problems)
    # TODO: Factor out checks or use mock problems object
    try:
      trip.AddStopTimeObject(transitfeed.StopTime(self.problems, stop1, arrival_secs=15), problems=self.problems)
      self.fail('OtherProblem exception expected')
    except transitfeed.OtherProblem:
      pass
    trip.AddStopTimeObject(transitfeed.StopTime(self.problems, stop1), problems=self.problems)
    try:
      trip.AddStopTimeObject(transitfeed.StopTime(self.problems, stop1, arrival_secs=15), problems=self.problems)
      self.fail('OtherProblem exception expected')
    except transitfeed.OtherProblem:
      pass
    trip.AddStopTimeObject(transitfeed.StopTime(self.problems, stop1, arrival_secs=30), problems=self.problems)


class TripStopTimeAccessorsTestCase(unittest.TestCase):
  def runTest(self):
    schedule = transitfeed.Schedule(
        problem_reporter=transitfeed.ExceptionProblemReporter())
    schedule.NewDefaultAgency(agency_name="Test Agency",
                              agency_url="http://example.com",
                              agency_timezone="America/Los_Angeles")
    route = schedule.AddRoute(short_name="54C", long_name="Polish Hill", route_type=3)

    service_period = schedule.GetDefaultServicePeriod()
    service_period.SetDateHasService("20070101")

    trip = route.AddTrip(schedule, 'via Polish Hill')

    stop1 = schedule.AddStop(36.425288, -117.133162, "Demo Stop 1")
    stop2 = schedule.AddStop(36.424288, -117.133142, "Demo Stop 2")

    trip.AddStopTime(stop1, arrival_time="5:11:00", departure_time="5:12:00")
    trip.AddStopTime(stop2, arrival_time="5:15:00", departure_time="5:16:00")

    # Add some more stop times and test GetEndTime does the correct thing
    self.assertEqual(transitfeed.FormatSecondsSinceMidnight(trip.GetStartTime()),
        "05:11:00")
    self.assertEqual(transitfeed.FormatSecondsSinceMidnight(trip.GetEndTime()),
        "05:16:00")

    trip.AddStopTime(stop1, departure_time="05:20:00")
    self.assertEqual(transitfeed.FormatSecondsSinceMidnight(trip.GetEndTime()),
        "05:20:00")

    trip.AddStopTime(stop2, arrival_time="05:22:00")
    self.assertEqual(transitfeed.FormatSecondsSinceMidnight(trip.GetEndTime()),
        "05:22:00")
    self.assertEqual(len(trip.GetStopTimesTuples()), 4)
    self.assertEqual(trip.GetStopTimesTuples()[0], (trip.trip_id, "05:11:00",
                                                    "05:12:00", stop1.stop_id, '1', '', '', '', ''))
    self.assertEqual(trip.GetStopTimesTuples()[3], (trip.trip_id, "05:22:00",
                                                    "", stop2.stop_id, '4', '', '', '', ''))


class BasicParsingTestCase(unittest.TestCase):
  """Checks that we're getting the number of child objects that we expect."""
  def runTest(self):
    loader = transitfeed.Loader(
      DataPath('good_feed.zip'),
      problems = transitfeed.ExceptionProblemReporter(),
      extra_validation = True)
    schedule = loader.Load()
    self.assertEqual(1, len(schedule._agencies))
    self.assertEqual(5, len(schedule.routes))
    self.assertEqual(2, len(schedule.service_periods))
    self.assertEqual(9, len(schedule.stops))
    self.assertEqual(11, len(schedule.trips))
    self.assertEqual(0, len(schedule.fare_zones))
    self.assertEqual('to airport', schedule.GetTrip('STBA').GetStopTimes()[0].stop_headsign)
    self.assertEqual(2, schedule.GetTrip('CITY1').GetStopTimes()[1].pickup_type)
    self.assertEqual(3, schedule.GetTrip('CITY1').GetStopTimes()[1].drop_off_type)


class RepeatedRouteNameTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectInvalidValue('repeated_route_name', 'route_long_name')


class InvalidRouteAgencyTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectInvalidValue('invalid_route_agency', 'agency_id')


class UndefinedStopAgencyTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectInvalidValue('undefined_stop', 'stop_id')


class SameShortLongNameTestCase(LoadTestCase):
  def runTest(self):
    self.ExpectInvalidValue('same_short_long_name', 'route_long_name')


class UnusedStopAgencyTestCase(unittest.TestCase):
  def runTest(self):
    loader = transitfeed.Loader(
      DataPath('unused_stop'),
      problems = transitfeed.ExceptionProblemReporter(),
      extra_validation = True)
    try:
      loader.Load()
      self.fail('UnusedStop exception expected')
    except transitfeed.UnusedStop, e:
      self.assertEqual("Bogus Stop (Demo)", e.stop_name)
      self.assertEqual("BOGUS", e.stop_id)
      pass


class OnlyCalendarDatesTestCase(unittest.TestCase):
  def runTest(self):
    loader = transitfeed.Loader(
      DataPath('only_calendar_dates'),
      problems = TestFailureProblemReporter(self),
      extra_validation = True)
    loader.Load()


class AddStopTimeParametersTestCase(unittest.TestCase):
  def runTest(self):
    stop = transitfeed.Stop()
    trip = transitfeed.Trip()
    trip.route_id = "SAMPLE_ID"
    trip.service_id = "WEEK"
    trip.trip_id = "SAMPLE_TRIP"

    trip.AddStopTime(stop)
    trip.AddStopTime(stop, arrival_secs=300, departure_secs=360)
    trip.AddStopTime(stop, arrival_time="00:07:00", departure_time="00:07:30")
    trip.Validate(TestFailureProblemReporter(self))


class DuplicateTripIDValidationTestCase(unittest.TestCase):
  def runTest(self):
    schedule = transitfeed.Schedule(
        problem_reporter=transitfeed.ExceptionProblemReporter())
    schedule.AddAgency("Sample Agency", "http://example.com",
                       "America/Los_Angeles")
    route = transitfeed.Route()
    route.route_id = "SAMPLE_ID"
    route.route_type = 3
    route.route_long_name = "Sample Route"
    schedule.AddRouteObject(route)

    service_period = transitfeed.ServicePeriod("WEEK")
    service_period.SetStartDate("20070101")
    service_period.SetEndDate("20071231")
    service_period.SetWeekdayService(True)
    schedule.AddServicePeriodObject(service_period)

    trip1 = transitfeed.Trip()
    trip1.route_id = "SAMPLE_ID"
    trip1.service_id = "WEEK"
    trip1.trip_id = "SAMPLE_TRIP"
    schedule.AddTripObject(trip1)

    trip2 = transitfeed.Trip()
    trip2.route_id = "SAMPLE_ID"
    trip2.service_id = "SATU"
    trip2.trip_id = "SAMPLE_TRIP"
    try:
      schedule.AddTripObject(trip2)
      self.fail("Expected Duplicate ID validation failure")
    except transitfeed.DuplicateID, e:
      self.assertEqual("trip_id", e.column_name)
      self.assertEqual("SAMPLE_TRIP", e.value)


class DuplicateStopValidationTestCase(ValidationTestCase):
  def runTest(self):
    schedule = transitfeed.Schedule(problem_reporter=self.problems)
    schedule.AddAgency("Sample Agency", "http://example.com",
                       "America/Los_Angeles")
    route = transitfeed.Route()
    route.route_id = "SAMPLE_ID"
    route.route_type = 3
    route.route_long_name = "Sample Route"
    schedule.AddRouteObject(route)

    service_period = transitfeed.ServicePeriod("WEEK")
    service_period.SetStartDate("20070101")
    service_period.SetEndDate("20071231")
    service_period.SetWeekdayService(True)
    schedule.AddServicePeriodObject(service_period)

    trip = transitfeed.Trip()
    trip.route_id = "SAMPLE_ID"
    trip.service_id = "WEEK"
    trip.trip_id = "SAMPLE_TRIP"
    schedule.AddTripObject(trip)

    stop1 = transitfeed.Stop()
    stop1.stop_id = "STOP1"
    stop1.stop_name = "Stop 1"
    stop1.stop_lat = 78.243587
    stop1.stop_lon = 32.258937
    schedule.AddStopObject(stop1)
    trip.AddStopTime(stop1, arrival_time="12:00:00", departure_time="12:00:00")

    stop2 = transitfeed.Stop()
    stop2.stop_id = "STOP2"
    stop2.stop_name = "Stop 2"
    stop2.stop_lat = 78.253587
    stop2.stop_lon = 32.258937
    schedule.AddStopObject(stop2)
    trip.AddStopTime(stop2, arrival_time="12:05:00", departure_time="12:05:00")
    schedule.Validate()

    stop3 = transitfeed.Stop()
    stop3.stop_id = "STOP3"
    stop3.stop_name = "Stop 3"
    stop3.stop_lat = 78.243587
    stop3.stop_lon = 32.268937
    schedule.AddStopObject(stop3)
    trip.AddStopTime(stop3, arrival_time="12:10:00", departure_time="12:10:00")
    schedule.Validate()

    stop4 = transitfeed.Stop()
    stop4.stop_id = "STOP4"
    stop4.stop_name = "Stop 4"
    stop4.stop_lat = 78.243588
    stop4.stop_lon = 32.268936
    schedule.AddStopObject(stop4)
    trip.AddStopTime(stop4, arrival_time="12:15:00", departure_time="12:15:00")
    self.ExpectOtherProblem(schedule)
    

class TempFileTestCaseBase(unittest.TestCase):
  """
  Subclass of TestCase which sets self.tempfilepath to a valid temporary zip
  file name and removes the file if it exists when the test is done.
  """
  def setUp(self):
    (fd, self.tempfilepath) = tempfile.mkstemp(".zip")
    # Open file handle causes an exception during remove in Windows
    os.close(fd)

  def tearDown(self):
    if os.path.exists(self.tempfilepath):
      os.remove(self.tempfilepath)


class MinimalWriteTestCase(TempFileTestCaseBase):
  """
  This test case simply constructs an incomplete feed with very few
  fields set and ensures that there are no exceptions when writing it out.
  
  This is very similar to TransitFeedSampleCodeTestCase below, but that one
  will no doubt change as the sample code is altered.
  """
  def runTest(self):
    schedule = transitfeed.Schedule()
    schedule.AddAgency("Sample Agency", "http://example.com",
                       "America/Los_Angeles")
    route = transitfeed.Route()
    route.route_id = "SAMPLE_ID"
    route.route_type = 3
    route.route_short_name = "66"
    route.route_long_name = "Sample Route acute letter e\202"
    schedule.AddRouteObject(route)

    service_period = transitfeed.ServicePeriod("WEEK")
    service_period.SetStartDate("20070101")
    service_period.SetEndDate("20071231")
    service_period.SetWeekdayService(True)
    schedule.AddServicePeriodObject(service_period)

    trip = transitfeed.Trip()
    trip.route_id = "SAMPLE_ID"
    trip.service_period = service_period
    trip.trip_id = "SAMPLE_TRIP"
    schedule.AddTripObject(trip)

    stop1 = transitfeed.Stop()
    stop1.stop_id = "STOP1"
    stop1.stop_name = u'Stop 1 acute letter e\202'
    stop1.stop_lat = 78.243587
    stop1.stop_lon = 32.258937
    schedule.AddStopObject(stop1)
    trip.AddStopTime(stop1, arrival_time="12:00:00", departure_time="12:00:00")

    stop2 = transitfeed.Stop()
    stop2.stop_id = "STOP2"
    stop2.stop_name = "Stop 2"
    stop2.stop_lat = 78.253587
    stop2.stop_lon = 32.258937
    schedule.AddStopObject(stop2)
    trip.AddStopTime(stop2, arrival_time="12:05:00", departure_time="12:05:00")

    schedule.Validate()
    schedule.WriteGoogleTransitFeed(self.tempfilepath)
    
    
class TransitFeedSampleCodeTestCase(unittest.TestCase):
  """
  This test should simply contain the sample code printed on the page:
  http://code.google.com/p/googletransitdatafeed/wiki/TransitFeed
  to ensure that it doesn't cause any exceptions.
  """
  def runTest(self):
    import transitfeed

    schedule = transitfeed.Schedule()
    schedule.AddAgency("Sample Agency", "http://example.com",
                       "America/Los_Angeles")
    route = transitfeed.Route()
    route.route_id = "SAMPLE_ID"
    route.route_type = 3
    route.route_short_name = "66"
    route.route_long_name = "Sample Route"
    schedule.AddRouteObject(route)

    service_period = transitfeed.ServicePeriod("WEEK")
    service_period.SetStartDate("20070101")
    service_period.SetEndDate("20071231")
    service_period.SetWeekdayService(True)
    schedule.AddServicePeriodObject(service_period)

    trip = transitfeed.Trip()
    trip.route_id = "SAMPLE_ID"
    trip.service_period = service_period
    trip.trip_id = "SAMPLE_TRIP"
    trip.direction_id = "0"
    trip.block_id = None
    schedule.AddTripObject(trip)

    stop1 = transitfeed.Stop()
    stop1.stop_id = "STOP1"
    stop1.stop_name = "Stop 1"
    stop1.stop_lat = 78.243587
    stop1.stop_lon = 32.258937
    schedule.AddStopObject(stop1)
    trip.AddStopTime(stop1, arrival_time="12:00:00", departure_time="12:00:00")

    stop2 = transitfeed.Stop()
    stop2.stop_id = "STOP2"
    stop2.stop_name = "Stop 2"
    stop2.stop_lat = 78.253587
    stop2.stop_lon = 32.258937
    schedule.AddStopObject(stop2)
    trip.AddStopTime(stop2, arrival_time="12:05:00", departure_time="12:05:00")

    schedule.Validate()  # not necessary, but helpful for finding problems
    schedule.WriteGoogleTransitFeed("new_feed.zip")
    

class AgencyIDValidationTestCase(unittest.TestCase):
  def runTest(self):
    schedule = transitfeed.Schedule(
        problem_reporter=transitfeed.ExceptionProblemReporter())
    route = transitfeed.Route()
    route.route_id = "SAMPLE_ID"
    route.route_type = 3
    route.route_long_name = "Sample Route"
    # no agency defined yet, failure.
    try:
      schedule.AddRouteObject(route)
      self.fail("Expected validation error")
    except transitfeed.InvalidValue, e:
      self.assertEqual('agency_id', e.field_name)
      self.assertEqual(None, e.value)

    # one agency defined, assume that the route belongs to it
    schedule.AddAgency("Test Agency", "http://example.com",
                       "America/Los_Angeles", "TEST_AGENCY")
    schedule.AddRouteObject(route)

    schedule.AddAgency("Test Agency 2", "http://example.com",
                       "America/Los_Angeles", "TEST_AGENCY_2")
    route = transitfeed.Route()
    route.route_id = "SAMPLE_ID_2"
    route.route_type = 3
    route.route_long_name = "Sample Route 2"
    # multiple agencies defined, don't know what omitted agency_id should be
    try:
      schedule.AddRouteObject(route)
      self.fail("Expected validation error")
    except transitfeed.InvalidValue, e:
      self.assertEqual('agency_id', e.field_name)
      self.assertEqual(None, e.value)

    # agency with no agency_id defined, matches route with no agency id
    schedule.AddAgency("Test Agency 3", "http://example.com",
                       "America/Los_Angeles")
    schedule.AddRouteObject(route)


class AddHeadwayPeriodValidationTestCase(ValidationTestCase):
  def ExpectInvalidValue(self, start_time, end_time, headway,
                         field_name, value):
    try:
      trip = transitfeed.Trip()
      trip.AddHeadwayPeriod(start_time, end_time, headway)
      self.fail("Expected InvalidValue error on %s" % field_name)
    except transitfeed.InvalidValue, e:
      self.assertEqual(field_name, e.field_name)
      self.assertEqual(value, e.value)
      self.assertEqual(0, len(trip.GetHeadwayPeriodTuples()))

  def ExpectMissingValue(self, start_time, end_time, headway, field_name):
    try:
      trip = transitfeed.Trip()
      trip.AddHeadwayPeriod(start_time, end_time, headway)
      self.fail("Expected MissingValue error on %s" % field_name)
    except transitfeed.MissingValue, e:
      self.assertEqual(field_name, e.field_name)
      self.assertEqual(0, len(trip.GetHeadwayPeriodTuples()))

  def runTest(self):
    # these should work fine
    trip = transitfeed.Trip()
    trip.trip_id = "SAMPLE_ID"
    trip.AddHeadwayPeriod(0, 50, 1200)
    trip.AddHeadwayPeriod("01:00:00", "02:00:00", "600")
    trip.AddHeadwayPeriod(u"02:00:00", u"03:00:00", u"1800")
    headways = trip.GetHeadwayPeriodTuples()
    self.assertEqual(3, len(headways))
    self.assertEqual((0, 50, 1200), headways[0])
    self.assertEqual((3600, 7200, 600), headways[1])
    self.assertEqual((7200, 10800, 1800), headways[2])
    self.assertEqual([("SAMPLE_ID", "00:00:00", "00:00:50", "1200"),
                      ("SAMPLE_ID", "01:00:00", "02:00:00", "600"),
                      ("SAMPLE_ID", "02:00:00", "03:00:00", "1800")],
                     trip.GetHeadwayPeriodOutputTuples())

    # now test invalid input
    self.ExpectMissingValue(None, 50, 1200, "start_time")
    self.ExpectMissingValue("", 50, 1200, "start_time")
    self.ExpectInvalidValue("midnight", 50, 1200, "start_time", "midnight")
    self.ExpectInvalidValue(-50, 50, 1200, "start_time", -50)
    self.ExpectMissingValue(0, None, 1200, "end_time")
    self.ExpectMissingValue(0, "", 1200, "end_time")
    self.ExpectInvalidValue(0, "noon", 1200, "end_time", "noon")
    self.ExpectInvalidValue(0, -50, 1200, "end_time", -50)
    self.ExpectMissingValue(0, 600, 0, "headway_secs")
    self.ExpectMissingValue(0, 600, None, "headway_secs")
    self.ExpectMissingValue(0, 600, "", "headway_secs")
    self.ExpectInvalidValue(0, 600, "test", "headway_secs", "test")
    self.ExpectInvalidValue(0, 600, -60, "headway_secs", -60)
    self.ExpectInvalidValue(0, 0, 1200, "end_time", 0)
    self.ExpectInvalidValue("12:00:00", "06:00:00", 1200, "end_time", 21600)


class MinimalUtf8Builder(TempFileTestCaseBase):
  def runTest(self):
    problems = TestFailureProblemReporter(self)
    schedule = transitfeed.Schedule(problem_reporter=problems)
    schedule.AddAgency("\xc8\x8b Fly Agency", "http://iflyagency.com",
                       "America/Los_Angeles")
    service_period = schedule.GetDefaultServicePeriod()
    service_period.SetDateHasService('20070101')
    # "u020b i with inverted accent breve" encoded in utf-8
    stop1 = schedule.AddStop(lng=140, lat=48.2, name="\xc8\x8b hub")
    # "u020b i with inverted accent breve" as unicode string
    stop2 = schedule.AddStop(lng=140.001, lat=48.201, name=u"remote \u020b station")
    route = schedule.AddRoute(u"\u03b2", "Beta", "Bus")
    trip = route.AddTrip(schedule, u"to remote \u020b station")
    trip.AddStopTime(stop1, departure_time='10:00:00')
    trip.AddStopTime(stop2, arrival_time='10:10:00')

    schedule.Validate(problems)
    schedule.WriteGoogleTransitFeed(self.tempfilepath)
    read_schedule = \
        transitfeed.Loader(self.tempfilepath, problems=problems,
                           extra_validation=True).Load()


class ScheduleBuilderTestCase(unittest.TestCase):
  def runTest(self):
    schedule = transitfeed.Schedule()

    schedule.AddAgency("Test Agency", "http://example.com",
                       "America/Los_Angeles")

    service_period = schedule.GetDefaultServicePeriod()
    self.assertTrue(service_period.service_id)
    service_period.SetWeekdayService(has_service=True)
    service_period.SetStartDate("20070320")
    service_period.SetEndDate("20071232")

    stop1 = schedule.AddStop(lng=-140.12, lat=48.921,
                             name="one forty at forty eight")
    stop2 = schedule.AddStop(lng=-140.22, lat=48.421, name="west and south")
    stop3 = schedule.AddStop(lng=-140.32, lat=48.121, name="more away")
    stop4 = schedule.AddStop(lng=-140.42, lat=48.021, name="more more away")

    route = schedule.AddRoute(short_name="R", long_name="My Route",
                              route_type="Bus")
    self.assertTrue(route.route_id)
    self.assertEqual(route.route_short_name, "R")
    self.assertEqual(route.route_type, 3)

    trip = route.AddTrip(schedule, headsign="To The End",
                         service_period=service_period)
    trip_id = trip.trip_id
    self.assertTrue(trip_id)
    trip = schedule.GetTrip(trip_id)
    self.assertEqual("To The End", trip.trip_headsign)
    self.assertEqual(service_period, trip.service_period)

    trip.AddStopTime(stop=stop1, arrival_secs=3600*8, departure_secs=3600*8)
    trip.AddStopTime(stop=stop2)
    trip.AddStopTime(stop=stop3, arrival_secs=3600*8 + 60*15,
                     departure_secs=3600*8 + 60*15)
    trip.AddStopTime(stop=stop4, arrival_time="8:25:00",
                     departure_secs=3600*8 + 60*26, stop_headsign="Last stop",
                     pickup_type=1, drop_off_type=3)

    schedule.Validate()
    self.assertEqual(4, len(trip.GetTimeStops()))
    self.assertEqual(1, len(schedule.GetRouteList()))
    self.assertEqual(4, len(schedule.GetStopList()))


class WriteSampleFeedTestCase(TempFileTestCaseBase):
  def assertEqualTimeString(self, a, b):
    """Assert that a and b are equal, even if they don't have the same zero
    padding on the hour. IE 08:45:00 vs 8:45:00."""
    if a[1] == ':':
      a = '0' + a
    if b[1] == ':':
      b = '0' + b
    self.assertEqual(a, b)

  def assertEqualWithDefault(self, a, b, default):
    """Assert that a and b are equal. Treat None and default as equal."""
    if a == b:
      return
    if a in (None, default) and b in (None, default):
      return
    self.assertTrue(False, "a=%s b=%s" % (a, b))

  def runTest(self):
    problems = TestFailureProblemReporter(self)
    schedule = transitfeed.Schedule(problem_reporter=problems)
    agency = transitfeed.Agency()
    agency.agency_id = "DTA"
    agency.agency_name = "Demo Transit Authority"
    agency.agency_url = "http://google.com"
    agency.agency_timezone = "America/Los_Angeles"
    schedule.AddAgencyObject(agency)

    routes = []
    route_data = [
        ("AB", "DTA", "10", "Airport - Bullfrog", 3),
        ("BFC", "DTA", "20", "Bullfrog - Furnace Creek Resort", 3),
        ("STBA", "DTA", "30", "Stagecoach - Airport Shuttle", 3),
        ("CITY", "DTA", "40", "City", 3),
        ("AAMV", "DTA", "50", "Airport - Amargosa Valley", 3)
      ]

    for route_entry in route_data:
      route = transitfeed.Route()
      (route.route_id, route.agency_id, route.route_short_name,
       route.route_long_name, route.route_type) = route_entry
      routes.append(route)
      schedule.AddRouteObject(route)

    shape_data = [
      (36.915760, -116.751709),
      (36.905018, -116.763206),
      (36.902134, -116.777969),
      (36.904091, -116.788185),
      (36.883602, -116.814537),
      (36.874523, -116.795593),
      (36.873302, -116.786491),
      (36.869202, -116.784241),
      (36.868515, -116.784729),
    ]

    shape = transitfeed.Shape("BFC1S")
    for (lat, lon) in shape_data:
      shape.AddPoint(lat, lon)
    schedule.AddShapeObject(shape)

    week_period = transitfeed.ServicePeriod()
    week_period.service_id = "FULLW"
    week_period.start_date = "20070101"
    week_period.end_date = "20071231"
    week_period.SetWeekdayService()
    week_period.SetWeekendService()
    week_period.SetDateHasService("20070604", False)
    schedule.AddServicePeriodObject(week_period)

    weekend_period = transitfeed.ServicePeriod()
    weekend_period.service_id = "WE"
    weekend_period.start_date = "20070101"
    weekend_period.end_date = "20071231"
    weekend_period.SetWeekendService()
    schedule.AddServicePeriodObject(weekend_period)

    stops = []
    stop_data = [
        ("FUR_CREEK_RES", "Furnace Creek Resort (Demo)",
         36.425288, -117.133162),
        ("BEATTY_AIRPORT", "Nye County Airport (Demo)",
         36.868446, -116.784682),
        ("BULLFROG", "Bullfrog (Demo)", 36.88108, -116.81797),
        ("STAGECOACH", "Stagecoach Hotel & Casino (Demo)",
         36.915682, -116.751677),
        ("NADAV", "North Ave / D Ave N (Demo)", 36.914893, -116.76821),
        ("NANAA", "North Ave / N A Ave (Demo)", 36.914944, -116.761472),
        ("DADAN", "Doing AVe / D Ave N (Demo)", 36.909489, -116.768242),
        ("EMSI", "E Main St / S Irving St (Demo)", 36.905697, -116.76218),
        ("AMV", "Amargosa Valley (Demo)", 36.641496, -116.40094),
      ]
    for stop_entry in stop_data:
      stop = transitfeed.Stop()
      (stop.stop_id, stop.stop_name, stop.stop_lat, stop.stop_lon) = stop_entry
      schedule.AddStopObject(stop)
      stops.append(stop)

    trip_data = [
        ("AB", "FULLW", "AB1", "to Bullfrog", "0", "1", None),
        ("AB", "FULLW", "AB2", "to Airport", "1", "2", None),
        ("STBA", "FULLW", "STBA", "Shuttle", None, None, None),
        ("CITY", "FULLW", "CITY1", None, "0", None, None),
        ("CITY", "FULLW", "CITY2", None, "1", None, None),
        ("BFC", "FULLW", "BFC1", "to Furnace Creek Resort", "0", "1", "BFC1S"),
        ("BFC", "FULLW", "BFC2", "to Bullfrog", "1", "2", None),
        ("AAMV", "WE", "AAMV1", "to Amargosa Valley", "0", None, None),
        ("AAMV", "WE", "AAMV2", "to Airport", "1", None, None),
        ("AAMV", "WE", "AAMV3", "to Amargosa Valley", "0", None, None),
        ("AAMV", "WE", "AAMV4", "to Airport", "1", None, None),
      ]

    trips = []
    for trip_entry in trip_data:
      trip = transitfeed.Trip()
      (trip.route_id, trip.service_id, trip.trip_id, trip.trip_headsign,
       trip.direction_id, trip.block_id, trip.shape_id) = trip_entry
      trips.append(trip)
      schedule.AddTripObject(trip)

    stop_time_data = {
        "STBA": [("6:00:00", "6:00:00", "STAGECOACH", None, None, None, None),
                 ("6:20:00", "6:20:00", "BEATTY_AIRPORT", None, None, None, None)],
        "CITY1": [("6:00:00", "6:00:00", "STAGECOACH", 1.34, 0, 0, "stop 1"),
                  ("6:05:00", "6:07:00", "NANAA", 2.40, 1, 2, "stop 2"),
                  ("6:12:00", "6:14:00", "NADAV", 3.0, 2, 2, "stop 3"),
                  ("6:19:00", "6:21:00", "DADAN", 4, 2, 2, "stop 4"),
                  ("6:26:00", "6:28:00", "EMSI", 5.78, 2, 3, "stop 5")],
        "CITY2": [("6:28:00", "6:28:00", "EMSI", None, None, None, None),
                  ("6:35:00", "6:37:00", "DADAN", None, None, None, None),
                  ("6:42:00", "6:44:00", "NADAV", None, None, None, None),
                  ("6:49:00", "6:51:00", "NANAA", None, None, None, None),
                  ("6:56:00", "6:58:00", "STAGECOACH", None, None, None, None)],
        "AB1": [("8:00:00", "8:00:00", "BEATTY_AIRPORT", None, None, None, None),
                ("8:10:00", "8:15:00", "BULLFROG", None, None, None, None)],
        "AB2": [("12:05:00", "12:05:00", "BULLFROG", None, None, None, None),
                ("12:15:00", "12:15:00", "BEATTY_AIRPORT", None, None, None, None)],
        "BFC1": [("8:20:00", "8:20:00", "BULLFROG", None, None, None, None),
                 ("9:20:00", "9:20:00", "FUR_CREEK_RES", None, None, None, None)],
        "BFC2": [("11:00:00", "11:00:00", "FUR_CREEK_RES", None, None, None, None),
                 ("12:00:00", "12:00:00", "BULLFROG", None, None, None, None)],
        "AAMV1": [("8:00:00", "8:00:00", "BEATTY_AIRPORT", None, None, None, None),
                  ("9:00:00", "9:00:00", "AMV", None, None, None, None)],
        "AAMV2": [("10:00:00", "10:00:00", "AMV", None, None, None, None),
                  ("11:00:00", "11:00:00", "BEATTY_AIRPORT", None, None, None, None)],
        "AAMV3": [("13:00:00", "13:00:00", "BEATTY_AIRPORT", None, None, None, None),
                  ("14:00:00", "14:00:00", "AMV", None, None, None, None)],
        "AAMV4": [("15:00:00", "15:00:00", "AMV", None, None, None, None),
                  ("16:00:00", "16:00:00", "BEATTY_AIRPORT", None, None, None, None)],
      }

    for trip_id, stop_time_list in stop_time_data.items():
      for stop_time_entry in stop_time_list:
        (arrival_time, departure_time, stop_id, shape_dist_traveled,
            pickup_type, drop_off_type, stop_headsign) = stop_time_entry
        trip = schedule.GetTrip(trip_id)
        stop = schedule.GetStop(stop_id)
        trip.AddStopTime(stop, arrival_time=arrival_time,
                         departure_time=departure_time,
                         shape_dist_traveled=shape_dist_traveled,
                         pickup_type=pickup_type, drop_off_type=drop_off_type,
                         stop_headsign=stop_headsign)

    self.assertEqual(0, schedule.GetTrip("CITY1").GetStopTimes()[0].pickup_type)
    self.assertEqual(1, schedule.GetTrip("CITY1").GetStopTimes()[1].pickup_type)

    headway_data = [
        ("STBA", "6:00:00", "22:00:00", 1800),
        ("CITY1", "6:00:00", "7:59:59", 1800),
        ("CITY2", "6:00:00", "7:59:59", 1800),
        ("CITY1", "8:00:00", "9:59:59", 600),
        ("CITY2", "8:00:00", "9:59:59", 600),
        ("CITY1", "10:00:00", "15:59:59", 1800),
        ("CITY2", "10:00:00", "15:59:59", 1800),
        ("CITY1", "16:00:00", "18:59:59", 600),
        ("CITY2", "16:00:00", "18:59:59", 600),
        ("CITY1", "19:00:00", "22:00:00", 1800),
        ("CITY2", "19:00:00", "22:00:00", 1800),
      ]

    headway_trips = {}
    for headway_entry in headway_data:
      (trip_id, start_time, end_time, headway) = headway_entry
      headway_trips[trip_id] = []  # adding to set to check later
      trip = schedule.GetTrip(trip_id)
      trip.AddHeadwayPeriod(start_time, end_time, headway, problems)
    for trip_id in headway_trips:
      headway_trips[trip_id] = \
          schedule.GetTrip(trip_id).GetHeadwayPeriodTuples()

    fare_data = [
        ("p", 1.25, "USD", 0, 0),
        ("a", 5.25, "USD", 0, 0),
      ]

    fares = []
    for fare_entry in fare_data:
      fare = transitfeed.Fare(fare_entry[0], fare_entry[1], fare_entry[2],
                              fare_entry[3], fare_entry[4])
      fares.append(fare)
      schedule.AddFareObject(fare)

    fare_rule_data = [
        ("p", "AB"),
        ("p", "STBA"),
        ("p", "BFC"),
        ("a", "AAMV"),
      ]

    for fare_rule_entry in fare_rule_data:
      rule = transitfeed.FareRule(fare_rule_entry[0], fare_rule_entry[1])
      schedule.AddFareRuleObject(rule, problems)

    schedule.Validate(problems)
    schedule.WriteGoogleTransitFeed(self.tempfilepath)

    read_schedule = \
        transitfeed.Loader(self.tempfilepath, problems=problems,
                           extra_validation=True).Load()

    self.assertEqual(1, len(read_schedule.GetAgencyList()))
    self.assertEqual(agency, read_schedule.GetAgency(agency.agency_id))

    self.assertEqual(len(routes), len(read_schedule.GetRouteList()))
    for route in routes:
      self.assertEqual(route, read_schedule.GetRoute(route.route_id))

    self.assertEqual(2, len(read_schedule.GetServicePeriodList()))
    self.assertEqual(week_period,
                     read_schedule.GetServicePeriod(week_period.service_id))
    self.assertEqual(weekend_period,
                     read_schedule.GetServicePeriod(weekend_period.service_id))

    self.assertEqual(len(stops), len(read_schedule.GetStopList()))
    for stop in stops:
      self.assertEqual(stop, read_schedule.GetStop(stop.stop_id))

    self.assertEqual(len(trips), len(read_schedule.GetTripList()))
    for trip in trips:
      self.assertEqual(trip, read_schedule.GetTrip(trip.trip_id))

    for trip_id in headway_trips:
      self.assertEqual(headway_trips[trip_id],
                       read_schedule.GetTrip(trip_id).GetHeadwayPeriodTuples())

    for trip_id, stop_time_list in stop_time_data.items():
      trip = read_schedule.GetTrip(trip_id)
      read_stoptimes = trip.GetStopTimes()
      self.assertEqual(len(read_stoptimes), len(stop_time_list))
      for stop_time_entry, read_stoptime in zip(stop_time_list, read_stoptimes):
        (arrival_time, departure_time, stop_id, shape_dist_traveled,
            pickup_type, drop_off_type, stop_headsign) = stop_time_entry
        self.assertEqual(stop_id, read_stoptime.stop_id)
        self.assertEqual(read_schedule.GetStop(stop_id), read_stoptime.stop)
        self.assertEqualTimeString(arrival_time, read_stoptime.arrival_time)
        self.assertEqualTimeString(departure_time, read_stoptime.departure_time)
        self.assertEqual(shape_dist_traveled, read_stoptime.shape_dist_traveled)
        self.assertEqualWithDefault(pickup_type, read_stoptime.pickup_type, 0)
        self.assertEqualWithDefault(drop_off_type, read_stoptime.drop_off_type, 0)
        self.assertEqualWithDefault(stop_headsign, read_stoptime.stop_headsign, '')

    self.assertEqual(len(fares), len(read_schedule.GetFareList()))
    for fare in fares:
      self.assertEqual(fare, read_schedule.GetFare(fare.fare_id))

    self.assertEqual(1, len(read_schedule.GetShapeList()))
    self.assertEqual(shape, read_schedule.GetShape(shape.shape_id))

# TODO: test GetStopTimeTrips
# TODO: test GetPattern

class DefaultAgencyTestCase(unittest.TestCase):
  def freeAgency(self, ex=''):
    agency = transitfeed.Agency()
    agency.agency_id = 'agencytestid' + ex
    agency.agency_name = 'Foo Bus Line' + ex
    agency.agency_url = 'http://gofoo.com/' + ex
    agency.agency_timezone='America/Los_Angeles'
    return agency

  def test_SetDefault(self):
    schedule = transitfeed.Schedule()
    agency = self.freeAgency()
    schedule.SetDefaultAgency(agency)
    self.assertEqual(agency, schedule.GetDefaultAgency())

  def test_NewDefaultAgency(self):
    schedule = transitfeed.Schedule()
    agency1 = schedule.NewDefaultAgency()
    self.assertTrue(agency1.agency_id)
    self.assertEqual(agency1.agency_id, schedule.GetDefaultAgency().agency_id)
    self.assertEqual(1, len(schedule.GetAgencyList()))
    agency2 = schedule.NewDefaultAgency()
    self.assertTrue(agency2.agency_id)
    self.assertEqual(agency2.agency_id, schedule.GetDefaultAgency().agency_id)
    self.assertEqual(2, len(schedule.GetAgencyList()))
    self.assertNotEqual(agency1, agency2)
    self.assertNotEqual(agency1.agency_id, agency2.agency_id)

    agency3 = schedule.NewDefaultAgency(agency_id='agency3',
                                        agency_name='Agency 3',
                                        agency_url='http://goagency')
    self.assertEqual(agency3.agency_id, 'agency3')
    self.assertEqual(agency3.agency_name, 'Agency 3')
    self.assertEqual(agency3.agency_url, 'http://goagency')
    self.assertEqual(agency3, schedule.GetDefaultAgency())
    self.assertEqual('agency3', schedule.GetDefaultAgency().agency_id)
    self.assertEqual(3, len(schedule.GetAgencyList()))

  def test_NoAgencyMakeNewDefault(self):
    schedule = transitfeed.Schedule()
    agency = schedule.GetDefaultAgency()
    self.assertTrue(isinstance(agency, transitfeed.Agency))
    self.assertTrue(agency.agency_id)
    self.assertEqual(1, len(schedule.GetAgencyList()))
    self.assertEqual(agency, schedule.GetAgencyList()[0])
    self.assertEqual(agency.agency_id, schedule.GetAgencyList()[0].agency_id)

  def test_AssumeSingleAgencyIsDefault(self):
    schedule = transitfeed.Schedule()
    agency1 = self.freeAgency()
    schedule.AddAgencyObject(agency1)
    agency2 = self.freeAgency('2')  # don't add to schedule
    # agency1 is default because it is the only Agency in schedule
    self.assertEqual(agency1, schedule.GetDefaultAgency())

  def test_MultipleAgencyCausesNoDefault(self):
    schedule = transitfeed.Schedule()
    agency1 = self.freeAgency()
    schedule.AddAgencyObject(agency1)
    agency2 = self.freeAgency('2')
    schedule.AddAgencyObject(agency2)
    self.assertEqual(None, schedule.GetDefaultAgency())

  def test_OverwriteExistingAgency(self):
    schedule = transitfeed.Schedule()
    agency1 = self.freeAgency()
    agency1.agency_id = '1'
    schedule.AddAgencyObject(agency1)
    agency2 = schedule.NewDefaultAgency()
    # Make sure agency1 was not overwritten by the new default
    self.assertEqual(agency1, schedule.GetAgency(agency1.agency_id))
    self.assertNotEqual('1', agency2.agency_id)


class FindUniqueIdTestCase(unittest.TestCase):
  def test_simple(self):
    d = {}
    for i in range(0, 5):
      d[transitfeed.FindUniqueId(d)] = 1
    k = d.keys()
    k.sort()
    self.assertEqual(('0', '1', '2', '3', '4'), tuple(k))

  def test_AvoidCollision(self):
    d = {'1': 1}
    d[transitfeed.FindUniqueId(d)] = 1
    self.assertEqual(2, len(d))
    self.assertFalse('2' in d, "Ops, next statement should add something to d")
    d['2'] = None
    d[transitfeed.FindUniqueId(d)] = 1
    self.assertEqual(4, len(d))


class DefaultServicePeriodTestCase(unittest.TestCase):
  def test_SetDefault(self):
    schedule = transitfeed.Schedule()
    service1 = transitfeed.ServicePeriod()
    service1.SetDateHasService('20070101', True)
    service1.service_id = 'SERVICE1'
    schedule.SetDefaultServicePeriod(service1)
    self.assertEqual(service1, schedule.GetDefaultServicePeriod())
    self.assertEqual(service1, schedule.GetServicePeriod(service1.service_id))

  def test_NewDefault(self):
    schedule = transitfeed.Schedule()
    service1 = schedule.NewDefaultServicePeriod()
    self.assertTrue(service1.service_id)
    schedule.GetServicePeriod(service1.service_id)
    service1.SetDateHasService('20070101', True)  # Make service1 different
    service2 = schedule.NewDefaultServicePeriod()
    schedule.GetServicePeriod(service2.service_id)
    self.assertTrue(service1.service_id)
    self.assertTrue(service2.service_id)
    self.assertNotEqual(service1, service2)
    self.assertNotEqual(service1.service_id, service2.service_id)

  def test_NoServicesMakesNewDefault(self):
    schedule = transitfeed.Schedule()
    service1 = schedule.GetDefaultServicePeriod()
    self.assertEqual(service1, schedule.GetServicePeriod(service1.service_id))

  def test_AssumeSingleServiceIsDefault(self):
    schedule = transitfeed.Schedule()
    service1 = transitfeed.ServicePeriod()
    service1.SetDateHasService('20070101', True)
    service1.service_id = 'SERVICE1'
    schedule.AddServicePeriodObject(service1)
    self.assertEqual(service1, schedule.GetDefaultServicePeriod())
    self.assertEqual(service1.service_id, schedule.GetDefaultServicePeriod().service_id)

  def test_MultipleServicesCausesNoDefault(self):
    schedule = transitfeed.Schedule()
    service1 = transitfeed.ServicePeriod()
    service1.service_id = 'SERVICE1'
    service1.SetDateHasService('20070101', True)
    schedule.AddServicePeriodObject(service1)
    service2 = transitfeed.ServicePeriod()
    service2.service_id = 'SERVICE2'
    service2.SetDateHasService('20070201', True)
    schedule.AddServicePeriodObject(service2)
    service_d = schedule.GetDefaultServicePeriod()
    self.assertEqual(service_d, None)

class ApproximateDistanceBetweenStopsTestCase(unittest.TestCase):
  def testEquator(self):
    stop1 = transitfeed.Stop(lat=0, lng=100,
                             name='Stop one', stop_id='1')
    stop2 = transitfeed.Stop(lat=0.01, lng=100.01,
                             name='Stop two', stop_id='2')
    self.assertAlmostEqual(
        transitfeed.ApproximateDistanceBetweenStops(stop1, stop2),
        1570, -1)  # Compare first 3 digits

  def testWhati(self):
    stop1 = transitfeed.Stop(lat=63.1, lng=-117.2,
                             name='Stop whati one', stop_id='1')
    stop2 = transitfeed.Stop(lat=63.102, lng=-117.201,
                             name='Stop whati two', stop_id='2')
    self.assertAlmostEqual(
        transitfeed.ApproximateDistanceBetweenStops(stop1, stop2),
        228, 0)

if __name__ == '__main__':
  unittest.main()
