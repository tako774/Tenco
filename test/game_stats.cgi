#!/usr/bin/ruby

### ゲーム統計情報収集・保存CGI ###

# 開始時刻
now = Time.now
# リビジョン
REVISION = 'R0.10'

DEBUG = 1

# アプリケーションのトップディレクトリ
TOP_DIR = '..'

$LOAD_PATH.unshift "#{TOP_DIR}/common"
$LOAD_PATH.unshift "#{TOP_DIR}/entity"
$LOAD_PATH.unshift "#{TOP_DIR}/dao"

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
	require 'GameStat'
	
	db = nil   # DB接続
						
	# DB接続
	db = DB.getInstance

	res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

	# トランザクション開始
	db.exec("BEGIN TRANSACTION")		
	
	### ゲーム統計情報取得
	
	# ゲーム全体の対戦数取得・保存
	
	# 処理対象のゲームID取得
	require 'GameDao'
	game_dao = GameDao.new
	game_ids = game_dao.get_batch_target_ids
		
	res_body << "batch target game_ids selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# ゲームIDごとにレート計算実行
	game_ids.each do |game_id|
		res_body << "★GAME_ID:#{game_id} の処理\n"
	
		game_stat = GameStat.new         # ゲーム統計情報
		game_type1_stats = []	         # キャラごとの統計情報
		game_type1_vs_type1_stats = []   # キャラ・対戦キャラごとの統計情報
		
		# 既存レコードがあればDELETE 
		res = db.exec(<<-"SQL")
			DELETE FROM
			  game_stats
		    WHERE
		      game_id = #{game_id.to_i}
			;
		SQL
		
		# PostgreSQL8.3以下 は discinct より group by のほうが高速。読みづらいけど。
		res = db.exec(<<-"SQL")
		  INSERT INTO
			game_stats (
				game_id,
				date_time, 
				track_records_count, 
				matched_track_records_count,
				matched_accounts_count,
				matched_accounts_type1s_count
			)
			SELECT
			  #{game_id.to_i} AS game_id,
			  LOCALTIMESTAMP AS date_time,
			  gas.track_records_count AS track_records_count,
			  gas.matched_track_records_count AS matched_track_records_count,
			  gads.matched_accounts_count AS matched_accounts_count,
			  gatds.matched_accounts_type1s_count AS matched_accounts_type1s_count
			FROM
			  (
				SELECT
				  SUM(track_records_count) AS track_records_count,
				  SUM(matched_track_records_count) AS matched_track_records_count
				FROM
				  game_daily_stats 
				WHERE 
				  game_id = #{game_id.to_i}
			  ) AS gas,
			  (
				SELECT
				  count(*) AS matched_accounts_count
				FROM (
				  SELECT
					1
				  FROM
					game_account_daily_stats 
				  WHERE 
					game_id = #{game_id.to_i}
				  GROUP BY
					game_id,
					account_id
				) gads2
			  ) AS gads,
			  (
          SELECT
            count(*) AS matched_accounts_type1s_count
          FROM
            game_account_ratings gar
          WHERE
            gar.game_id = #{game_id.to_i}
            AND gar.type1_id IN (
              SELECT
                type1_id
              FROM
                game_type1s
              WHERE
                game_id = #{game_id.to_i}
            )
			  ) AS gatds
		  RETURNING *
		SQL
		
		res.num_fields.times do |i|
			game_stat.instance_variable_set("@#{res.fields[i]}", res[0][i])
		end
		
		res.clear
		
		res_body << "総対戦結果数 #{game_stat.track_records_count} 件\n"
		res_body << "マッチ済み対戦結果数 #{game_stat.matched_track_records_count} 件\n"
		res_body << "マッチ済みアカウント数 #{game_stat.matched_accounts_count} 件\n"
		res_body << "マッチ済みアカウント・キャラ数 #{game_stat.matched_accounts_type1s_count} 件\n"
		res_body << "game_stat inserted ...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
		# キャラ別対戦結果情報取得・保存
		res = db.exec(<<-"SQL")
		  DELETE FROM
		    game_type1_stats
		  WHERE
		    game_id = #{game_id.to_i}
		  ;
		SQL
		
    res = db.exec(<<-"SQL")
      INSERT INTO
        game_type1_stats (game_id, type1_id, date_time, track_records_count, accounts_count, wins, loses)
      SELECT
        #{game_id.to_i} AS game_id,
        gtds.type1_id   AS type1_id,
        LOCALTIMESTAMP  AS date_time,
        gtds.track_records_count AS track_records_count,
        gatds.accounts_count     AS accounts_count,
        gtds.wins   AS wins,
        gtds.loses  AS loses
      FROM
      (
        SELECT
          type1_id,
          SUM(track_records_count) AS track_records_count,
          SUM(wins) AS wins,
          SUM(loses) AS loses
        FROM
          game_type1_daily_stats
        WHERE
          game_id = #{game_id.to_i}
        GROUP BY
          type1_id
      ) AS gtds,
      (
        SELECT
          type1_id, count(account_id) AS accounts_count
        FROM
          game_account_ratings
        WHERE
          game_id = #{game_id.to_i}
          AND type1_id IN (SELECT type1_id FROM game_type1s WHERE game_id = #{game_id.to_i})
        GROUP BY
          type1_id
        ORDER BY
          type1_id
      ) AS gatds
      WHERE
        gtds.type1_id = gatds.type1_id
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
		  SELECT
			#{game_id.to_i} AS game_id,
			type1_id,
			matched_type1_id,
			LOCALTIMESTAMP AS date_time,
			SUM(track_records_count) AS track_records_count,
			SUM(wins) AS wins,
			SUM(loses) AS loses
		  FROM
			game_type1_vs_type1_daily_stats
		  WHERE
			game_id = #{game_id.to_i}
		  GROUP BY
			game_id, type1_id, matched_type1_id
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
		
		# UPDATE or INSERT
		gtvts_inserted_counts = 0
		gtvts_updated_counts = 0
		
		game_type1_vs_type1_stats.each do |gtvts| 
		
			res_update = db.exec(<<-"SQL")
			  UPDATE
				game_type1_vs_type1_stats
			  SET
				date_time = to_timestamp(#{s gtvts.date_time.to_s}, \'YYYY-MM-DD HH24:MI:SS\'),
				track_records_count = #{gtvts.track_records_count.to_i},
				wins = #{gtvts.wins.to_i},
				loses = #{gtvts.loses.to_i},
				updated_at = now(),
				lock_version = lock_version + 1
			  WHERE
				game_id = #{gtvts.game_id.to_i}
				AND type1_id = #{gtvts.type1_id.to_i}
				AND matched_type1_id = #{gtvts.matched_type1_id.to_i}
			  RETURNING *;
			SQL
			
			# UPDATE 失敗時は INSERT
			if res_update.num_tuples != 1 then
				res_insert = db.exec(<<-"SQL")
				  INSERT INTO
				    game_type1_vs_type1_stats (game_id, type1_id, matched_type1_id, date_time, track_records_count, wins, loses)
				  VALUES (
				    #{gtvts.game_id.to_i},
				    #{gtvts.type1_id.to_i},
				    #{gtvts.matched_type1_id.to_i},
				    to_timestamp(#{s gtvts.date_time.to_s}, \'YYYY-MM-DD HH24:MI:SS\'),
				    #{gtvts.track_records_count.to_i},
				    #{gtvts.wins.to_i},
					#{gtvts.loses.to_i}
				  )
				  RETURNING *;
				SQL
				
				if res_insert.num_tuples != 1 then
					raise "UPDATE 失敗後の INSERT に失敗しました。"
				else
					gtvts_inserted_counts += 1
				end
				res_insert.clear
			
			else
				gtvts_updated_counts += 1
			end
			 
			res_update.clear
		end

		
		res_body << "キャラ別・対戦キャラ別対戦結果情報 #{gtvts_inserted_counts} 件のデータを登録、#{gtvts_updated_counts} 件のデータを更新しました\n"
		res_body << "game_type1_vs_type1_stats updated/inserted ...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
	end
	
	# コミット
	db.exec("COMMIT")
	res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
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

res_body << "process finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

begin
	# HTTP レスポンス送信
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
