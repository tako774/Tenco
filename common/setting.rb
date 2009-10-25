# -*- coding: utf-8 -*-
### 設定クラス
require 'yaml'

class Setting
	@@config_file = "#{File::dirname(__FILE__)}/../../../config/config.yaml"

	def initialize
		@_setting = YAML.load_file(@@config_file)
	end
	
	def [] (key)
		@_setting[key]
	end
end
