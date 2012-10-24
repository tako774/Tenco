#!/usr/bin/ruby

### アカウントプロフィール画像更新 ###

begin
  # 開始時刻
  now = Time.now
  # リビジョン
  REVISION = 'R0.00'

  DEBUG = 1

  # アプリケーションのトップディレクトリ
  TOP_DIR = '..'

  $LOAD_PATH.unshift "#{TOP_DIR}/common"

  require 'time'
  require 'logger'
  require 'utils'
  require 'db'

  require "#{TOP_DIR}/dao/ExServiceAccountDao"
  require "#{TOP_DIR}/common/twitter_client"

  source = ""

  # ログファイルパス
  LOG_PATH = "../log/rating_#{now.strftime('%Y%m%d')}.log"
  ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

  # HTTP/HTTPSレスポンス文字列
  res_status = ''
  res_header = ''
  res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

rescue
  print "Status: 500 Internal Server Error\n"
  print "content-type: text/plain\n\n"
  print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
  #print ex.to_s
  #print ex.backtrace.join("\n").to_s
end

begin
  res_body << "Start...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

  # 設定
  EX_SERVICE_NAME_TWITTER = 'twitter'
  
  # DB 接続
  db = DB.getInstance
  # twitter クライアント取得
  tw = TwitterClient.get_instance
  
  # トランザクション開始
  db.exec("BEGIN TRANSACTION")
  
  res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

  # 処理対象のアカウント取得
  esa_dao = ExServiceAccountDao.new
  update_ex_service_accounts = esa_dao.get_request_update_flag_on_by_ex_service_name(EX_SERVICE_NAME_TWITTER)
  update_ex_service_account_keys = update_ex_service_accounts.map { |a| a.account_key }
   
  res_body << "#{update_ex_service_accounts.length} 件の更新要求のある twitter アカウント情報を取得\n"
  res_body << "update_ex_service_accounts selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
  
  # アカウントの twitter 情報取得
  twitter_users = {} # screen_name.downcase => Twitter::User
  
  begin
    twitter_users = tw.users(update_ex_service_account_keys).inject({}) do |hash, twitter_user|
      hash.update({twitter_user[:screen_name].downcase => twitter_user})
    end
  rescue Twitter::Error::NotFound
  end

  res_body << "#{twitter_users.length} 件の twitter アカウント情報を取得\n"
  res_body << "twitter user info collected ...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
  
  # twitter 情報保存
  update_ex_service_accounts.each do |ex_service_account|
    if twitter_user = twitter_users[ex_service_account.account_key.downcase] then
      ex_service_account.profile_image_url = twitter_user[:profile_image_url].sub(/_normal(\.[^.]+||)\z/, '\1')
    end
    ex_service_account.request_update_flag = 0
    esa_dao.update ex_service_account
  end
  
  res_body << "twitter user info DB updated ...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
  
  # コミット
  db.exec("COMMIT")
  res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
  
rescue => ex
  res_status = "Status: 500 Server Error\n" unless res_status
  res_body << "twitter アカウント情報の更新時にエラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
  File.open(ERROR_LOG_PATH, 'a') do |log|
    log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
    log.puts source
    log.puts ex.class
    log.puts ex.to_s
    log.puts ex.backtrace.join("/n").to_s
    log.puts
  end
else
  res_status = "Status: 200 OK\n" unless res_status
  res_body << "twitter アカウント情報の更新正常終了。\n"
ensure
  # DB接続を閉じる
  db.close if db
end

# 実行時間
times = Process.times
res_body << "実行時間 #{Time.now - now}秒, CPU時間 #{times.utime + times.stime}秒\n"
  
# HTTP レスポンス送信
res_status = "Status: 500 Internal Server Error\n" unless res_status
res_header = "content-type:text/plain; charset=utf-8\n"
if ENV['REQUEST_METHOD'] == 'GET' then
  print res_status
  print res_header
  print "\n"
end
print res_body

# ログ書き込み
File.open(LOG_PATH, 'a') do |log|
  log.puts "#{now.iso8601} #{File::basename(__FILE__)} Rev.#{REVISION}"
  log.puts "Total Time: #{Time.now - now}"
  log.puts res_status
  log.puts res_header
  log.puts "\n"
  log.puts res_body
  log.puts "----"
end


exit