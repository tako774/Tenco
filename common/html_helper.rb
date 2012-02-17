# -*- coding: utf-8 -*-
### HTMLヘルパーモジュール

require 'erubis'

module HTMLHelper

	include Erubis::XmlHelper
	
	# twitter 画像（リンク付き）HTML生成
	def twitter_image_html(screen_name, size = "mini")
		return <<-"HTML"
<a href="http://twitter.com/#{h screen_name}" target="_blank"><img
  src="https://api.twitter.com/1/users/profile_image?screen_name=#{h screen_name}&amp;size=#{size}"
  alt=""
  title="twitter @#{h screen_name}"
  width="24"
  height="24"
  /></a>
		HTML
	end
	
end

include HTMLHelper