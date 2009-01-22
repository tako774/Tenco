### DB接続シングルトン
# require 'rubygems' # XREA サーバーでは不要
require 'postgres'
require 'yaml'

CONFIG = YAML.load_file("#{File::dirname(__FILE__)}/../../../config/db.yaml")

class DB
	@@revision = 'R0.02'
	@@db = nil
	attr_reader :con
	
	private_class_method :new
	def initialize
		# DBコネクト取得
		@con = PGconn.connect(CONFIG[:host], CONFIG[:port], "", "", CONFIG[:database], CONFIG[:username], CONFIG[:password])
	end

	def self.getInstance
		@@db = new unless @@db
		return @@db
	end
	
	def exec(sql)
		@con.exec(sql) if @con
	end
	
	def close
		@con.close if @con
	end
end
