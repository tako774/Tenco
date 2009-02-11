### ユーティリティモジュール
module Utils
	# SQL エスケープ
	def sql_escape(p)
		"E'" + p.to_s.gsub(/\\/, '\&\&').gsub(/'/, "''") + "'"
	end
	
	alias s sql_escape
	
	# 改行を<br />に変換
	def lf2html(str)
		return	str.gsub(/\n/, "<br />\n")
	end
	
	# Time.parse が重過ぎるので代用のメソッド
	# YYYY-MM-DD HH:MM:SS[.fragments] を想定
	def pgsql_timestamp_str_to_time(timestamp_str)
		t, frag = timestamp_str.split(/[\.]/)
		
		# 秒以下があれば別途扱う
		if frag then
			frag = "0.#{frag}".to_f * 1000000
		else
			frag = 0
		end
		
		ta = t.split(/[\- :]/)
		ta.push frag

		return Time.local(*ta)
	end
end

