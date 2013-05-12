# -*- coding: utf-8 -*-
### HTMLヘルパーモジュール

require 'erubis'

module HTMLHelper

	include Erubis::XmlHelper
  
	# プレイヤー画像（リンク付き）HTML生成
	def player_image_html(twitter_data)
		return <<-"HTML"
<a href="#{h twitter_data[:url]}" target="_blank"><img
  src="#{h twitter_data[:player_image_url]}"
  alt=""
  title="twitter @#{h twitter_data[:screen_name]}"
  width="128px"
  /></a>
		HTML
	end
	
	# twitter アイコン画像（リンク付き）HTML生成
	def icon_image_html(twitter_data)
		return <<-"HTML"
<a href="#{h twitter_data[:url]}" target="_blank"><img
  src="#{h twitter_data[:icon_image_url]}"
  alt=""
  title="twitter @#{h twitter_data[:screen_name]}"
  width="24px"
  height="24px"
  /></a>
		HTML
	end
	
  # スラッシュを省いて url エンコード
  def u_except_slash(text)
    text.split("/").map{ |s| u s }.join("/")
  end
  
end

include HTMLHelper