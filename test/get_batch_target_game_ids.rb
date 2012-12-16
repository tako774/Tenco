#!/usr/bin/ruby
# coding:utf-8

begin

  # 開始時刻
  now = Time.now

  ### バッチ対象ゲームID取得 ###
  REVISION = '0.01'
  DEBUG = 1

  $LOAD_PATH.unshift '../common'
  $LOAD_PATH.unshift '../entity'
  $LOAD_PATH.unshift '../dao'

  require 'kconv'
  require 'yaml'
  require 'time'

  require 'db'

  # ログファイルパス
  LOG_PATH = "../log/rating_#{now.strftime('%Y%m%d')}.log"
  ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

  # 設定
  LIST_SEPARATOR = ' '
  
  # DB接続
  require 'db'
  db = DB.getInstance()
    
  # 処理対象のゲームID取得
  require 'GameDao'
  game_ids = GameDao.new.get_batch_target_ids
  
  puts game_ids.join(LIST_SEPARATOR)
  
rescue => ex
  File.open(ERROR_LOG_PATH, 'a') do |log|
    log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
    log.puts ex.class
    log.puts ex.to_s
    log.puts ex.backtrace.join("\n").to_s
    log.puts
  end
ensure
  # DB接続を閉じる
  db.close if db
  # ログ書き込み
  File.open(LOG_PATH, 'a') do |log|
    log.puts "#{now.iso8601} #{File::basename(__FILE__)} Rev.#{REVISION}"
    log.puts "Total Time: #{Time.now - now}"
    log.puts game_ids.join(LIST_SEPARATOR) if game_ids
    log.puts "----"
  end
end
