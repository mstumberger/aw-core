import logging
import unittest
from datetime import datetime, timedelta, timezone

from aw_core.models import Event
from aw_transform import filter_period_intersect, filter_keyvals, sort_by_timestamp, sort_by_duration, merge_events_by_keys, split_url_events


class IncludeLabelsTest(unittest.TestCase):
    def test_filter_keyval(self):
        labels = ["a", "c"]
        events = [
            Event(data={"label": "a"}),
            Event(data={"label": "b"}),
            Event(data={"label": "c"}),
        ]
        included_events = filter_keyvals(events, "label", labels)
        excluded_events = filter_keyvals(events, "label", labels, exclude=True)
        assert len(included_events) == 2
        assert len(excluded_events) == 1


class FilterPeriodIntersectTest(unittest.TestCase):
    def test_filter_period_intersect(self):
        td1h = timedelta(hours=1)
        td30min = timedelta(minutes=30)
        now = datetime.now()

        # Filter 1h event with another 1h event at a 30min offset
        to_filter = [Event(timestamp=now, duration=td1h)]
        filter_with = [Event(timestamp=now + timedelta(minutes=30), duration=td1h)]
        filtered_events = filter_period_intersect(to_filter, filter_with)
        assert filtered_events[0].duration == timedelta(minutes=30)

        # Filter 2x 30min events with a 15min gap with another 45min event in between intersecting both
        to_filter = [
            Event(timestamp=now, duration=td30min),
            Event(timestamp=now + timedelta(minutes=45), duration=td30min)
        ]
        filter_with = [
            Event(timestamp=now + timedelta(minutes=15), duration=timedelta(minutes=45))
        ]
        filtered_events = filter_period_intersect(to_filter, filter_with)
        assert len(filtered_events) == 2
        assert filtered_events[0].duration == timedelta(minutes=15)
        assert filtered_events[1].duration == timedelta(minutes=15)

        # Same as previous intersection, but reversing filter and to_filter events
        to_filter = [
            Event(timestamp=now + timedelta(minutes=15), duration=timedelta(minutes=45))
        ]
        filter_with = [
            Event(timestamp=now, duration=td30min),
            Event(timestamp=now + timedelta(minutes=45), duration=td30min)
        ]
        filtered_events = filter_period_intersect(to_filter, filter_with)
        assert len(filtered_events) == 2
        assert filtered_events[0].duration == timedelta(minutes=15)
        assert filtered_events[1].duration == timedelta(minutes=15)


class SortEventsTests(unittest.TestCase):
    def test_sort_by_timestamp(self):
        now = datetime.now(timezone.utc)
        events = []
        events.append(Event(timestamp=now+timedelta(seconds=2), duration=timedelta(seconds=1)))
        events.append(Event(timestamp=now+timedelta(seconds=1), duration=timedelta(seconds=2)))
        events_sorted = sort_by_timestamp(events)
        assert events_sorted == events[::-1]

    def test_sort_by_duration(self):
        now = datetime.now(timezone.utc)
        events = []
        events.append(Event(timestamp=now+timedelta(seconds=2), duration=timedelta(seconds=1)))
        events.append(Event(timestamp=now+timedelta(seconds=1), duration=timedelta(seconds=2)))
        events_sorted = sort_by_duration(events)
        assert events_sorted == events[::-1]


class MergeEventsByKeys(unittest.TestCase):
    def test_merge_events_by_keys_1(self):
        now = datetime.now(timezone.utc)
        events = []
        e1_data = {"label": "a"}
        e2_data = {"label": "b"}
        e1 = Event(data=e1_data, timestamp=now, duration=timedelta(seconds=1))
        e2 = Event(data=e2_data, timestamp=now, duration=timedelta(seconds=1))
        events = events + [e1]*10
        events = events + [e2]*5
        result = merge_events_by_keys(events, ["label"])
        result = sort_by_duration(result)
        print(result)
        print(len(result))
        assert len(result) == 2
        assert result[0].duration == timedelta(seconds=10)
        assert result[1].duration == timedelta(seconds=5)

    def test_merge_events_by_keys_2(self):
        now = datetime.now(timezone.utc)
        events = []
        e1_data = {"k1": "a", "k2": "a"}
        e2_data = {"k1": "a", "k2": "c"}
        e3_data = {"k1": "b", "k2": "a"}
        e1 = Event(data=e1_data, timestamp=now, duration=timedelta(seconds=1))
        e2 = Event(data=e2_data, timestamp=now, duration=timedelta(seconds=1))
        e3 = Event(data=e3_data, timestamp=now, duration=timedelta(seconds=1))
        events = events + [e1]*10
        events = events + [e2]*9
        events = events + [e3]*8
        result = merge_events_by_keys(events, ["k1", "k2"])
        result = sort_by_duration(result)
        print(result)
        print(len(result))
        assert len(result) == 3
        assert result[0].data == e1_data
        assert result[0].duration == timedelta(seconds=10)
        assert result[1].data == e2_data
        assert result[1].duration == timedelta(seconds=9)
        assert result[2].data == e3_data
        assert result[2].duration == timedelta(seconds=8)

class URLParseEventTransform(unittest.TestCase):
    def test_url_parse_event(self):
        now = datetime.now(timezone.utc)
        e = Event(data={"url": "http://asd.com/test/?a=1"}, timestamp=now, duration=timedelta(seconds=1))
        result = split_url_events([e])
        print(result)
        assert result[0].data["protocol"] == "http"
        assert result[0].data["domain"] == "asd.com"
        assert result[0].data["path"] == "/test/"
        assert result[0].data["params"] == ""
        assert result[0].data["options"] == "a=1"
        assert result[0].data["identifier"] == ""

        e2 = Event(data={"url": "https://www.asd.asd.com/test/test2/meh;meh2?asd=2&asdf=3#id"}, timestamp=now, duration=timedelta(seconds=1))
        result = split_url_events([e2])
        print(result)
        assert result[0].data["protocol"] == "https"
        assert result[0].data["domain"] == "asd.asd.com"
        assert result[0].data["path"] == "/test/test2/meh"
        assert result[0].data["params"] == "meh2"
        assert result[0].data["options"] == "asd=2&asdf=3"
        assert result[0].data["identifier"] == "id"

        e3 = Event(data={"url": "file:///home/johan/myfile.txt"}, timestamp=now, duration=timedelta(seconds=1))
        result = split_url_events([e3])
        print(result)
        assert result[0].data["protocol"] == "file"
        assert result[0].data["domain"] == ""
        assert result[0].data["path"] == "/home/johan/myfile.txt"
        assert result[0].data["params"] == ""
        assert result[0].data["options"] == ""
        assert result[0].data["identifier"] == ""
