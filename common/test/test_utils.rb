### ユーティリティモジュールのテスト
require 'test/unit'
require '../utils'
include Utils
require 'time'
require 'kconv'

class Test_Utils < Test::Unit::TestCase
	
	def test_sql_escape
		assert_equal("E''''\n", <<-"SQL")
#{s "'"}
		SQL
		
		assert_equal("E'\\\\'\n", <<-"SQL")
#{s "\\"}
		SQL
		
		assert_equal("E'\n'\n", <<-"SQL")
#{s "\n"}
		SQL
		
		assert_equal("E'anything'' OR ''x''=''x'\n", <<-"SQL")
#{s "anything' OR 'x'='x"}
		SQL
		
		assert_equal("E'x'' AND email IS NULL; --'\n", <<-"SQL")
#{s "x' AND email IS NULL; --"}
		SQL
		
		assert_equal("E'x'' AND 1=(SELECT COUNT(*) FROM tabname); --'\n", <<-"SQL")
#{s "x' AND 1=(SELECT COUNT(*) FROM tabname); --"}
		SQL
	end
	
	def test_iso8601_to_time
		time_str = "2008-12-06T21:11:19.234+09:00"
		t1 = iso8601_to_time(time_str)
		t2 = Time.parse(time_str)
		assert_equal(t2, t1)
	end
	
end
