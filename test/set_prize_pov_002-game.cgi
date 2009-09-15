#!/usr/bin/ruby

### pov2-game:ゲーム別マッチング数ランキングの達成記録の保存 ###
begin

# 開始時刻
now = Time.now

REVISION = '0.02'
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
	res_body << "pov2-game:ゲーム別マッチング数ランキング処理開始\n"

	# 設定
	pov_id = 2
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
		game_account_ratings = [] # マッチ済みアカウント数情報
		rank_member_count = 0  # ランキング対象キャラ総数
		class1_rank_limit = 200 # クラス１の値下限
		class2_rank_limit = 100 # クラス２の値下限
		class3_rank_limit = 50  # クラス３の値下限
	
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
		
		# ゲーム全体のマッチングアカウント数情報を、マッチングアカウント数降順で取得
		# ランダムは除く
		require 'GameAccountRating'
		res = db.exec(<<-"SQL")
			SELECT 
			  r.account_id, r.type1_id, r.matched_accounts
			FROM 
			  game_account_ratings r
			WHERE
			  r.game_id = #{game_id.to_i}
			  AND r.type1_id != #{SEG_V[:virtual_type1][:random][:value].to_i}
			  AND r.matched_accounts >= #{class3_rank_limit}
			ORDER BY
			  r.matched_accounts DESC
		SQL
		
		res.each do |r|
			gar = GameAccountRating.new
			res.num_fields.times do |i|
				gar.instance_variable_set("@#{res.fields[i]}", r[i])
			end
			game_account_ratings << gar
		end
		res.clear	
		
		res_body << "#{game_account_ratings.length} 件のマッチ済みアカウント数情報を取得\n"
		res_body << "game account ratings selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 結果をDBに保存
		begin
			require 'PrizeAccount'
			game_account_ratings.each do |gar|
				
				# 更新後のクラスを算出
				game_pov_class_id = nil
				matched_accounts = gar.matched_accounts.to_i
				
				case matched_accounts
				when 0 .. class3_rank_limit - 1
					game_pov_class_id = 0
				when class3_rank_limit .. (class2_rank_limit - 1)
					game_pov_class_id = GAME_POV_CLASS[:high_game_type1_ratings_ranker][:tertiary][:value]
				when class2_rank_limit .. (class1_rank_limit - 1)
					game_pov_class_id = GAME_POV_CLASS[:high_game_type1_ratings_ranker][:secondary][:value]
				else
					game_pov_class_id = GAME_POV_CLASS[:high_game_type1_ratings_ranker][:primary][:value]
				end
				
				# 更新または作成。クラスが変わらない場合、時刻は更新しない。
				res_update = db.exec(<<-"SQL")
					UPDATE
					  prize_accounts
					SET
					  game_pov_class_id = #{game_pov_class_id.to_i},
					  date_time =
						CASE game_pov_class_id
						  WHEN #{game_pov_class_id.to_i} THEN date_time
						  ELSE CURRENT_TIMESTAMP
						END,
					  updated_at = CURRENT_TIMESTAMP,
					  lock_version = lock_version + 1
					WHERE
					  prize_id = #{prizes[0].id}
					  AND account_id = #{gar.account_id}
					  AND type1_id = #{gar.type1_id}
					RETURNING id
				SQL
								
				# UPDATE 失敗時は INSERT
				if res_update.num_tuples != 1 then
					res_update.clear
					res_insert = db.exec(<<-"SQL")
					  INSERT INTO
						prize_accounts
						(
						  prize_id,
						  account_id,
						  type1_id,
						  date_time,
						  game_pov_class_id
						)
					  VALUES
						(
						  #{prizes[0].id.to_i},
						  #{gar.account_id.to_i},
						  #{gar.type1_id.to_i},
						  CURRENT_TIMESTAMP,
						  #{game_pov_class_id.to_i}
						)
					  RETURNING id;
					SQL
					
					if res_insert.num_tuples != 1 then
						res_insert.clear
						raise "UPDATE 失敗後の INSERT に失敗しました。"
					end
					
					res_insert.clear
				else
					res_update.clear
				end
				
			end
			
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