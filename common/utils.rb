# -*- coding: utf-8 -*-
### ユーティリティモジュール
require 'kakasi'
include Kakasi
require 'nkf'
require 'uri'

NG_WORDS = File.read("#{File::dirname(__FILE__)}/../../../config/ng_words_list.txt").split("\n")
NG_WORDS_REGEXP = Regexp.new(NG_WORDS.join("|"))

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
		
	# 文字列正規化
	# 大文字→小文字
	# カタカナ→ひらがな
	# 半角カナ→ひらがな
	# 全角英数記号→半角英数記号
	def str_norm(str)
		NKF.nkf('-w -E -m0 -x', kakasi('-Ea -kH -KH -i euc', NKF.nkf('-e -W -m0 -x', str))).downcase
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
	def pgsql_timestamp_str_to_time(str)
		frag_str = str[20,6]
		frag = "0.#{frag_str}".to_f * 1000000 if frag_str
		return Time.local(str[0,4], str[5,2], str[8,2], str[11,2], str[14,2], str[17,2], frag)
	end
	
	# 特定文字列の伏字化
	def hide_ng_words(str, alt = "**")
		str.gsub(NG_WORDS_REGEXP, alt)
	end
	
	# 虹色変換
	def col_rainbow(rate, start_arg = 0.0, end_arg = 360.0)
		r = nil
		g = nil
		b = nil
		
		f = (((end_arg - start_arg) * rate + start_arg) % 360.0) / 60.0
		
		if (0 <= f && f <= 6) then
			if (1 <= f && f < 2) then
				r = 255 * (2 - f)
			elsif (2 <= f && f < 4) then
				r = 0
			elsif (4 <= f && f < 5) then
				r = 255 * (f - 4)
			else
				r = 255
			end

			if (0 <= f && f < 1) then
				g = 255 * f
			elsif (1 <= f && f < 3) then
				g = 255
			elsif (3 <= f && f < 4) then
				g = 255 * (4 - f)
			else
				g = 0
			end

			if (0 <= f && f < 2) then
				b = 0
			elsif (2 <= f && f < 3) then
				b = 255 * (f - 2)
			elsif (3 <= f && f <= 5) then
				b = 255
			else
				b = 255 * (6 - f)
			end
			
			return [r.round, g.round, b.round]
		else
			return [nil, nil, nil]
		end
	end
	
	# HTTP/HTTPS URI 形式チェック
	def validate_uri(str)
		str =~ URI.regexp && $& == str ? true : false
	end
end

include Utils
