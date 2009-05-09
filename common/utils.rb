### ユーティリティモジュール
require 'kakasi'
include Kakasi
require 'nkf'

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
	
	# XHTML空白文字（半角スペース/タブ/CR/LF）を&nbsp;に変換
	def xhtml_sp2nbsp(str)
		return	str.gsub(/\s|\t|\r\n|\r|\n/, "&nbsp;")
	end
	
	# 全角カナを半角カナに変換
	def z2h(str)
		NKF.nkf('-w -E -m0 -x', kakasi('-Kk -i euc', NKF.nkf('-e -W -m0 -x', str))) 
	end
	
	# 引数の文字列が指定された文字数より長い場合に、全角カナを半角カナに変換
	def z2h_long_str(str, limit_length = 8)
		if str.split(//u).length > limit_length then
			str = z2h(str)
		end
		return str
	end
	
	# クエリストリング分解
	def parse_query_str(str)
		query = {}
		str.to_s.split(/[;&]/).each do |q|
		  key, val = q.split(/=/, 2)
		  query[key] = val.gsub(/\+/," ").gsub(/%[a-fA-F\d]{2}/){ $&[1,2].hex.chr } if val
		end
		return query
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
