#!/usr/bin/ruby

### pov1-game:ゲーム別レートランキングの達成記録の保存 ###
begin

# 開始時刻
now = Time.now

REVISION = '0.05'
DEBUG = 1

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../entity'

require 'time'
require 'logger'
require 'utils'
include Utils
require 'db'

require 'segment_const'
require 'pov_class_const' # POV クラス定数

# ログファイルパス
LOG_PATH = "../log/rating_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# HTTP/HTTPSレスポンス文字列
res_status = ''
res_header = ''
res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n"

# 引数
source = ''

rescue
	print "Status: 500 Internal Server Error\n"
	print "content-type: text/plain\n\n"
	print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
	#print ex.to_s
	#print ex.backtrace.join("\n").to_s
end

begin
	res_body << "pov1-game:ゲーム別レートランキング処理開始\n"

	# 設定
	pov_id = 1
	pov_eval_unit_seg = SEG_V[:pov_eval_unit][:game][:value].to_i
	
	game_povs = [] # 処理対象の game_pov
	
	# DB接続
	db = DB.getInstance
	# トランザクション開始
	db.exec("BEGIN TRANSACTION")
	
	res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
	# 処理対象の game_pov_id の取得
	require 'GamePov'
	res = db.exec(<<-"SQL")
		SELECT
		  gp.id, g.id
		FROM
		  game_povs gp,
		  games g
		WHERE
		  gp.pov_id = #{pov_id.to_i}
		  AND gp.pov_eval_unit_seg = #{pov_eval_unit_seg.to_i}
		  AND gp.game_id = g.id
		  AND g.is_batch_target = 1
	SQL
	
	res.each do |r|
		gp = GamePov.new
		gp.id = r[0].to_i
		gp.game_id = r[1].to_i
		game_povs << gp
	end
	res.clear	
	
	res_body << "Game POV ids selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# game_pov_id ごとに処理
	game_povs.each do |gp|
		game_pov_id = gp.id
		game_id = gp.game_id
		
		res_body << "★Game POV ID:#{game_pov_id} の処理\n"
		
		# 変数
		prizes = [] # プライズ情報
		game_account_ratings = [] # レーティング情報
		rank_member_count = 0  # ランキング対象キャラ総数
		class1_rank_limit = 1  # クラス１の順位下限
		class2_rank_limit = 20 # クラス２の順位下限
		class3_ratio = 0.05    # クラス３の上位割合
		class3_rank_limit = 0  # クラス３の順位下限
	
		# プライズ情報を取得
		require 'Prize'
		res = db.exec(<<-"SQL")
			SELECT
			  *
			FROM
			  prizes
			WHERE
			  game_pov_id = #{game_pov_id.to_i}
		SQL
		
		if res.num_tuples < 1 then
			res.clear
			res_status = "Status: 500 Server Error\n"
			res_body << "該当プライズ情報がありません\n"
			next
		else
			res.each do |r|
				prize = Prize.new
				res.num_fields.times do |i|
					prize.instance_variable_set("@#{res.fields[i]}", r[i])
				end
				prizes << prize
			end
			res.clear	
		end
		
		res_body << "#{prizes.length} 件のプライズ情報を取得。\n"
		res_body << "prizes selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# ゲーム全体のレートランキング情報を、ランキング順で取得
		require 'GameAccountRating'
		res = db.exec(<<-"SQL")
			SELECT 
			  r.account_id, r.type1_id, r.game_type1_ratings_rank
			FROM 
			  game_account_ratings r
			WHERE
			  r.game_id = #{game_id.to_i}
			ORDER BY
			  r.game_type1_ratings_rank
		SQL
		
		res.each do |r|
			gar = GameAccountRating.new
			res.num_fields.times do |i|
				gar.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			game_account_ratings << gar
		end
		res.clear	
		
		res_body << "#{game_account_ratings.length} 件のレートランキング情報を取得。\n"
		res_body << "game account ratings selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# ランク対象アカウント・キャラ数取得
		res = db.exec(<<-"SQL")
			SELECT 
			  count(id) AS count
			FROM 
			  game_account_ratings r
			WHERE
			  r.game_id = #{game_id.to_i}
			  AND r.game_type1_ratings_rank > 0
		SQL
		
		if res.num_tuples < 1 then
			res.clear
			res_status = "Status: 500 Server Error\n"
			res_body << "ランク対象アカウントがありません\n"
			next
		else
			rank_member_count = res[0][0].to_i
			res.clear	
		end
		
		class3_rank_limit = (rank_member_count * class3_ratio).floor
		
		res_body << "レートランク対象キャラ数から、クラスごとのアカウント数を決定しました\n"
		
		res_body << "ratings rank counts selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 結果をDBに保存
		
		# 既存のプライズアカウント情報を取得
		prize_accounts = {}
		
		res = db.exec(<<-"SQL")
			SELECT 
			  account_id,
			  type1_id,
			  game_pov_class_id
			FROM 
			  prize_accounts pa
			WHERE
			  pa.prize_id = #{prizes[0].id}
		SQL
		
		res.each do |r|
			prize_accounts[r[0]] ||= {}
			prize_accounts[r[0]][r[1]] ||= {}
			prize_accounts[r[0]][r[1]] = r[2]
		end
		
		res_body << "#{res.num_tuples} 件のプライズアカウント情報を取得。\n"
		
		res.clear
		
		res_body << "existing prize_accounts selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		begin
			res_update = db.exec(<<-"SQL")
				PREPARE
				  update_prize_accounts(int, int, int, int)
				AS
				  UPDATE
					prize_accounts
				  SET
					game_pov_class_id = $1,
					date_time =
					  CASE game_pov_class_id
						WHEN $1 THEN date_time
						ELSE CURRENT_TIMESTAMP
					  END,
					updated_at = CURRENT_TIMESTAMP,
					lock_version = lock_version + 1
				  WHERE
					prize_id = $2
					AND account_id = $3
					AND type1_id = $4
				  RETURNING id
			SQL
				
			inserted_count = 0
			updated_count = 0
			skip_count = 0
			game_account_ratings.each do |gar|
				
				# 更新後のクラスを算出
				game_pov_class_id = nil
				rank = gar.game_type1_ratings_rank.to_i
				
				case rank
				when 0
					game_pov_class_id = 0
				when class1_rank_limit
					game_pov_class_id = GAME_POV_CLASS[:high_game_type1_ratings_ranker][:primary][:value]
				when (class1_rank_limit + 1) .. class2_rank_limit
					game_pov_class_id = GAME_POV_CLASS[:high_game_type1_ratings_ranker][:secondary][:value]
				when (class2_rank_limit + 1) .. class3_rank_limit
					game_pov_class_id = GAME_POV_CLASS[:high_game_type1_ratings_ranker][:tertiary][:value]
				else
					game_pov_class_id = 4
				end
				
				# まだプライズアカウント情報レコードがなければ作成
				if !(prize_accounts[gar.account_id] && prize_accounts[gar.account_id][gar.type1_id]) then
					db.exec(<<-"SQL")
					  INSERT INTO
						prize_accounts
						(
						  prize_id,
						  account_id,
						  type1_id,
						  date_time,
						  game_pov_class_id
						)
					  SELECT
						#{prizes[0].id.to_i},
						#{gar.account_id.to_i},
						#{gar.type1_id.to_i},
						CURRENT_TIMESTAMP,
						#{game_pov_class_id.to_i}
					  WHERE
						NOT EXISTS (
						  SELECT
							*
						  FROM
							prize_accounts
						  WHERE
							prize_id = #{prizes[0].id.to_i}
							AND account_id = #{gar.account_id.to_i}
							AND type1_id = #{gar.type1_id.to_i}
						)
					SQL
					inserted_count += 1
				# クラスが変わっていれば更新
				elsif prize_accounts[gar.account_id][gar.type1_id].to_i != game_pov_class_id.to_i then
					res_update = db.exec(<<-"SQL")
					  EXECUTE update_prize_accounts(#{game_pov_class_id.to_i}, #{prizes[0].id}, #{gar.account_id}, #{gar.type1_id})
					SQL
					
					if res_update.num_tuples != 1 then
						raise "PrizeAccount テーブルのアップデート対象がありませんでした：#{prizes[0].id}, #{gar.account_id}, #{gar.type1_id}"
					else
						updated_count += 1
					end
					
					res_update.clear
					
				else
					skip_count += 1
				end
			end
			
			res_body << "更新 #{updated_count}件：登録 #{inserted_count}件:スキップ #{skip_count}件\n"
		rescue => ex
			res_status = "Status: 500 Server Error\n"
			res_body << "Game POV #{game_pov_id} プライズ達成情報保存時にエラーが発生しました。\n"
			raise ex
		else
			res_body << "Game POV #{game_pov_id} プライズ達成情報保存を正常に実行しました。\n"
		end
		
		res_body << "game pov #{game_pov_id} prize status stored...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	end
			
	# コミット
	db.exec("COMMIT")
	res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
	# アナライズ
	# db.exec("VACUUM ANALYZE")
	# res_body << "DB analyzed...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
	
rescue => ex
	res_status = "Status: 500 Server Error\n" unless res_status
	res_body << "プライズ達成情報更新時にエラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
	File.open(ERROR_LOG_PATH, 'a') do |log|
		log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
		log.puts source
		log.puts ex.to_s
		log.puts ex.backtrace.join("\n").to_s
		log.puts
	end
else
	res_status = "Status: 200 OK\n" unless res_status
	res_body << "プライズ達成情報更新正常終了。\n"
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
