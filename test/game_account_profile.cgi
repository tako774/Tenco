#!/usr/bin/ruby

### アカウントプロファイル情報収集・保存CGI ###

# 開始時刻
now = Time.now
# リビジョン
REVISION = 'R0.03'

DEBUG = 1

# アプリケーションのトップディレクトリ
TOP_DIR = '..'

$LOAD_PATH.unshift "#{TOP_DIR}/common"
$LOAD_PATH.unshift "#{TOP_DIR}/entity"

require 'time'
require 'logger'
require 'utils'
include Utils
require 'db'

# TOP ページ URL
TOP_URL = 'http://tenco.xrea.jp/'
# ログファイルパス
LOG_PATH = "#{TOP_DIR}/log/log_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "#{TOP_DIR}/log/error_#{now.strftime('%Y%m%d')}.log"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = ""

# ログ開始
logger = Logger.new(LOG_PATH)
logger.level = Logger::DEBUG

begin

	game_id = 1
	db = nil   # DB接続 
	game_accounts = []  # ゲームごとアカウント情報
						
	# DB接続
	db = DB.getInstance
	# トランザクション開始
	db.exec("BEGIN TRANSACTION")
	
	res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	### ゲーム・アカウントごとの画面表示名を決定
	# マッチ済み対戦結果から、もっともよく使っている名称を取得する
	
	# ゲーム・アカウント・使用名称ごとに、使用回数の降順で取得
	res = db.exec(<<-"SQL")
	  SELECT
		game_id AS game_id, player1_account_id AS account_id, player1_name AS rep_name, count(*) AS count
	  FROM
		track_records
	  WHERE
		matched_track_record_id IS NOT NULL
		AND game_id = #{game_id.to_i}
	  GROUP BY
		game_id, player1_account_id, player1_name
	  ORDER BY
		game_id, player1_account_id, count DESC
	SQL
	
	res_body << "#{res.num_tuples} 件のゲーム・アカウント・使用名称のデータをDBから取得しました\n"
	
	res_body << "game-account-name counts selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

	# 初出のゲームID・アカウントIDのみ取得
	require 'GameAccount'
	game_accounts_hash = {}
	res.each do |r|
		unless game_accounts_hash[r[0]] and game_accounts_hash[r[0]].key?(r[1]) then
			game_account = GameAccount.new
			res.num_fields.times do |i|
				game_account.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			game_accounts << game_account
			game_accounts_hash[r[0]] ||= {}
			game_accounts_hash[r[0]][r[1]] = 1
		end
	end
	game_accounts_hash = nil
	res.clear
	
	res_body << "#{game_accounts.length} 件のゲーム・アカウントごとの情報を取得しました。\n"
	
	res_body << "game_accounts created...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	updated_counts = 0
	inserted_counts = 0
	game_accounts.each do |a|
		# GameAccounts テーブルに Update or Insert
		res_update = db.exec(<<-"SQL")
		  UPDATE
			game_accounts g
		  SET
			rep_name = #{s a.rep_name},
			updated_at = now(),
			lock_version = g.lock_version + 1
		  WHERE
			g.account_id = #{a.account_id.to_i}
			AND g.game_id = #{a.game_id.to_i}
		  RETURNING *;
		SQL
		
		# UPDATE 失敗時は INSERT
		if res_update.num_tuples != 1 then
			res_insert = db.exec(<<-"SQL")
			  INSERT INTO
				game_accounts
				(
				  account_id,
				  game_id,
				  rep_name
				)
			  VALUES
				(
				  #{a.account_id.to_i},
				  #{a.game_id.to_i},
				  #{s a.rep_name}
				)
			  RETURNING *;
			SQL
			
			if res_insert.num_tuples != 1 then
				raise "UPDATE 失敗後の INSERT に失敗しました。"
			else
				inserted_counts += 1
			end
			res_insert.clear
		
		else
			updated_counts += 1
		end
		 
		res_update.clear
	end
	
	res_body << "#{inserted_counts} 件のデータを登録、#{updated_counts} 件のデータを更新しました\n"
	
	res_body << "game_accounts updated or inserted...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# コミット
	db.exec("COMMIT")
	res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# アナライズ
	# db.exec("VACUUM ANALYZE game_accounts")
	# res_body << "DB analyzed...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
rescue => ex
	res_status = "Status: 500 Server Error\n" unless res_status
	res_body = "サーバーエラーです。ごめんなさい。\n" unless res_body
	File.open(ERROR_LOG_PATH, 'a') do |err_log|
		err_log.puts "#{now.to_s} #{File::basename(__FILE__)} #{REVISION}" 
		err_log.puts ENV['QUERY_STRING']
		err_log.puts ex.to_s
		err_log.puts ex.backtrace.join("\n").to_s
		err_log.puts
	end
ensure
	db.close if db
end

res_body << "process finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

begin
# レスポンス出力
res_status = "Status: 500 Internal Server Error\n" unless res_status
res_header = "content-type:text/plain; charset=utf-8\n" unless res_header
if ENV['REQUEST_METHOD'] == 'GET' then
	print res_status
	print res_header
	print "\n"
end
print res_body

# ログ記録
	times = Process.times
	logger.debug(
		[
			File::basename(__FILE__),
			REVISION,
			Time.now - now,
			times.utime + times.stime,
			times.utime,
			times.stime,
			times.cutime,
			times.cstime,
			is_cache_used.to_s,
			ENV['QUERY_STRING'].gsub(/\r\n|\n/, '\n')[0..99]
		].join("\t")
	)
rescue
end
