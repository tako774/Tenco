### ユーティリティモジュールのテスト
require 'test/unit'
require '../utils'
include Utils
require 'time'
require 'kconv'

class Test_Utils < Test::Unit::TestCase
	
	def test_z2h
		z1 = 'アイウエオ'		
		assert_equal('ｱｲｳｴｵ', z2h(z1))
	end
	
	def test_z2h_long_str	
		z1 = 'アイウエオ'		
		assert_equal('アイウエオ', z2h_long_str(z1))
		z1 = 'アイウエオガギグゲゴ'		
		assert_equal('ｱｲｳｴｵｶﾞｷﾞｸﾞｹﾞｺﾞ', z2h_long_str(z1))
		z1 = '漢字とカナまじりで'		
		assert_equal('漢字とｶﾅまじりで', z2h_long_str(z1))
	end
	
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
	
	def test_hide_ng_words
		assert_equal("ウルトラ**スモス", hide_ng_words("ウルトラマンコスモス"))
	end
	
	def test_pgsql_timestamp_str_to_time
		time_strs = [
			"2008-11-19 00:26:27",
			"2008-11-19 00:26:27.237314",
			"2008-11-19 00:26:27.2373"
		]
		time_strs.each do |s|
			time = Time.parse(s)
			assert_equal(time, pgsql_timestamp_str_to_time(s))
		end
	end
	
	def test_str_norm
		test_strs = [
			"０",
			"　ｱアあ＠ＡAaａ"
		]
		result_strs = [
			"0",
			" あああ@aaaa"
		]
		
		test_strs.each_index do |i|
			assert_equal(result_strs[i], str_norm(test_strs[i]))
		end
	end
end
