### ユーティリティモジュール
module Utils
	# SQL エスケープ
	def sql_escape(p)
		if p.class.to_s == 'String' then
			p = "E'" + p.gsub(/\'/, "''").gsub("\\", "\\\\\\\\") + "'"
		end
		return p
	end
	
	alias s sql_escape
	
	# 改行を<br />に変換
	def lf2html(str)
		return	str.gsub(/\n/, "<br />\n")
	end
	
	alias s sql_escape
	
	# Time.parse が重過ぎるので代用のメソッド
	# YYYY-MM-DDTHH:MM:SS[.fragments][[+-]MM:SS] を想定
	def iso8601_to_time(iso8601)
		if iso8601 =~ (/\A(.+?)([\+\-]\d{1,2}:\d{1,2})\z/) then
			iso8601 = $1 + "TZ" + $2
		end
		
		t, tz = iso8601.split(/TZ/)	
		
		t_shift = 0
		if tz =~ /\A([\+\-])(\d{1,2}):(\d{1,2})\z/ then
			t_shift = $2.to_i * 60 * 60 + $3.to_i * 60
			if ($1 == "+") then
				t_shift = -1 * t_shift
			end
		end
		
		t, frag = t.split(/[\.]/)
		
		# 秒以下があれば別途扱う
		if frag then
			frag = "0.#{frag}".to_f * 1000000
		else
			frag = 0
		end
		
		ta = t.split(/[\/\- :T]/)
		ta.push frag

		return (Time.utc(*ta) + t_shift).getlocal
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

