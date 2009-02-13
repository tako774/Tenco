### ユーティリティモジュール
NG_WORDS = File.read("#{File::dirname(__FILE__)}/../../../config/ng_words.txt").split("\n")

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
	
	# 特定文字列の伏字化
	def hide_ng_words(str, alt = "**")
		NG_WORDS.each do |w|
			str.gsub!(w, alt)
		end
		return str
	end
end
