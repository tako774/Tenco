### DB接続シングルトン
# require 'rubygems'
require 'pg'
require "#{File::dirname(__FILE__)}/pg-util"
require 'yaml'

CONFIG = YAML.load_file("#{File::dirname(__FILE__)}/../../../config/db.yaml")

class DB
	@@revision = 'R0.04'
	@@db = nil
	attr_reader :con
	
	private_class_method :new
	def initialize
		# DBコネクト取得
		@con = PGconn.connect(CONFIG[:host], CONFIG[:port], "", "", CONFIG[:database], CONFIG[:username], CONFIG[:password])
		# クライアント文字コード設定
		@con.set_client_encoding("utf-8")
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
