### DB接続シングルトン
# require 'rubygems'
require 'pg'
require 'pg-util'
require 'yaml'

CONFIG = YAML.load_file("#{File::dirname(__FILE__)}/../../../config/db.yaml")

class DB
	@@revision = 'R0.03'
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
	
	def async_exec(sql)
		@con.async_exec(sql) if @con
	end
	
	def query(sql)
		@con.query(sql) if @con
	end
	
	def async_query(sql)
		@con.async_query(sql) if @con
	end
	
	def close
		@con.close if @con
		@@db = nil
	end
	
	def reset
		@con.reset if @con
	end
end
