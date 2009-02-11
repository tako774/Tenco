require 'benchmark'
require 'time'
require '../utils'
include Utils

n = 100000
iso8601_time_str = '2009-02-09T11:23:45' 

Benchmark.bm do |bm|
	bm.report { n.times { Time.iso8601(iso8601_time_str) } }
	bm.report { n.times { iso8601_to_time(iso8601_time_str) } }
end

