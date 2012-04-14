# -*- coding: utf-8 -*-
### レート計算関係ユーティリティモジュール

module RatingUtil

	# 勝率から理論レート差に変換
	def win_rate2rating_diff(win_rate)
		rating_diff = nil
		
		if 0.0 < win_rate and win_rate < 1.0 then
			rating_diff = 400.0 * Math.log10(win_rate / (1.0 - win_rate))
		end
		
		return rating_diff
	end
	
	# レート差から理論勝率に変換
	def rating_diff2win_rate(rating_diff)
		return 1.0 / (1.0 + 10.0 ** (-1.0 * rating_diff / 400.0))
	end
	
end

include RatingUtil
