#!/usr/bin/ruby

### ゲーム統計情報収集・保存CGI ###

# 開始時刻
now = Time.now
# リビジョン
REVISION = 'R0.02'

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

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		require 'GameStat'
		
		game_id = 1
		db = nil   # DB接続
		
		game_stat = GameStat.new         # ゲーム統計情報
		game_type1_stats = []	         # キャラごとの統計情報
		game_type1_vs_type1_stats = []   # キャラ・対戦キャラごとの統計情報
							
		# DB接続
		db = DB.getInstance

		res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

		# トランザクション開始
		db.exec("BEGIN TRANSACTION")		
		
		### ゲーム統計情報取得
		
		# ゲーム全体の対戦数取得・保存
		
		# PostgreSQL は discinct より group by のほうが高速。読みづらいけど。
		res = db.exec(<<-"SQL")
		  INSERT INTO
		    game_stats (game_id, date_time, track_records_count, matched_track_records_count, accounts_count, matched_accounts_count, accounts_type1s_count, matched_accounts_type1s_count)
			  SELECT
			    game_id,
			    LOCALTIMESTAMP AS date_time,
				COUNT(*) AS track_records_count,
				SUM(
				  CASE
				    WHEN matched_track_record_id IS NOT NULL THEN 1
					ELSE 0
				  END
				) AS matched_track_records_count,
				(
				  SELECT
				    COUNT(*)
				  FROM 
				  (
				    SELECT
				      player1_account_id
				    FROM
				      track_records 
				    GROUP BY
				      player1_account_id
				  ) AS TEMP1
				) AS accounts_count,
				(
				  SELECT
				    COUNT(*)
				  FROM 
				  (
				    SELECT
				      player1_account_id
				    FROM
				      track_records
					WHERE
					  matched_track_record_id IS NOT NULL 
				    GROUP BY
				      player1_account_id
				  ) AS TEMP1
				) AS matched_accounts_count,
				(
				  SELECT
				    COUNT(*)
				  FROM 
				  (
				    SELECT
				      player1_account_id, player1_type1_id
				    FROM
				      track_records 
				    GROUP BY
				      player1_account_id, player1_type1_id
				  ) AS TEMP1
				) AS accounts_type1s_count,							
				(
				  SELECT
				    COUNT(*)
				  FROM 
				  (
				    SELECT
				      player1_account_id, player1_type1_id
				    FROM
				      track_records
				    WHERE
				      matched_track_record_id IS NOT NULL  
				    GROUP BY
				      player1_account_id, player1_type1_id
				  ) AS TEMP1
				) AS matched_accounts_type1s_count
			  FROM
				track_records
			  WHERE
				game_id = #{game_id.to_i}
			  GROUP BY
			    game_id
		  RETURNING *
		SQL
		
		res.num_fields.times do |i|
			game_stat.instance_variable_set("@#{res.fields[i]}", res[0][i])
		end
		
		res.clear
		
		res_body << "総対戦結果数 #{game_stat.track_records_count} 件\n"
		res_body << "マッチ済み対戦結果数 #{game_stat.matched_track_records_count} 件\n"
		res_body << "game_stat inserted ...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
			
		# キャラ別対戦結果情報取得・保存
		res = db.exec(<<-"SQL")
		  INSERT INTO
		    game_type1_stats (game_id, type1_id, date_time, track_records_count, accounts_count, wins, loses)
			  SELECT
			    game_id,
			    player1_type1_id AS type1_id,
			    LOCALTIMESTAMP AS date_time,
				COUNT(*) AS track_records_count,
				COUNT(DISTINCT(player1_account_id)) AS accounts_count,
				SUM(
				  CASE
				    WHEN player1_points > player2_points THEN 1
					ELSE 0
				  END
				) AS wins,
				SUM(
				  CASE
				    WHEN player1_points < player2_points THEN 1
					ELSE 0
				  END
				) AS loses
			  FROM
				track_records
			  WHERE
				game_id = #{game_id.to_i}
				AND matched_track_record_id IS NOT NULL
			  GROUP BY
			    game_id, player1_type1_id
		  RETURNING *
		SQL
		
		require 'GameType1Stat'
		res.each do |r|
			gts = GameType1Stat.new
			res.fields.length.times do |i|
				gts.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			game_type1_stats << gts
		end
		res.clear
		
		res_body << "キャラ別統計情報追加 #{game_type1_stats.length} 件\n"
		res_body << "game_type1_stats inserted ...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# キャラ別・対戦キャラ別対戦結果情報取得・保存
		res = db.exec(<<-"SQL")
		  INSERT INTO
		    game_type1_vs_type1_stats (game_id, type1_id, matched_type1_id, date_time, track_records_count, wins, loses)
			  SELECT
			    game_id,
				player1_type1_id AS type1_id,
				player2_type1_id AS matched_type1_id,
			    LOCALTIMESTAMP AS date_time,
				count(*) AS track_records_count,
				sum(
				  case
				    when player1_points > player2_points then 1
					else 0
				  end
				) AS wins,
				sum(
				  case
				    when player1_points < player2_points then 1
					else 0
				  end
				) AS loses
			  FROM
				track_records
			  WHERE
				game_id = #{game_id.to_i}
				AND matched_track_record_id IS NOT NULL
			  GROUP BY
			    game_id, player1_type1_id, player2_type1_id
		  RETURNING *;
		SQL
		
		require 'GameType1VsType1Stat'
		res.each do |r|
			gtvts = GameType1VsType1Stat.new
			res.fields.length.times do |i|
				gtvts.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			game_type1_vs_type1_stats << gtvts
		end
		res.clear
		
		res_body << "キャラ別・対戦キャラ別統計情報追加 #{game_type1_vs_type1_stats.length} 件\n"
		res_body << "game_type1_vs_type1_stats inserted ...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# コミット
		db.exec("COMMIT")
		res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# アナライズ
		db.exec("VACUUM ANALYZE")
		res_body << "DB analyzed...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		res_body << "サーバーエラーです。ごめんなさい。\n"
		res_body << "#{ex.to_s}\n"
		res_body << "#{ex.backtrace.join("\n")}\n"
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
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

res_body << "process finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

begin
# HTTP レスポンス送信
res_status = "Status: 500 Internal Server Error\n" unless res_status
res_header = "content-type:text/plain; charset=utf-8\n" unless res_header
print res_status
print res_header
print "\n"
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
