#!/usr/bin/ruby

# 開始時刻
now = Time.now

### 対戦結果I/F API ###
REVISION = 'R0.15'
DEBUG = false

$LOAD_PATH.unshift '../common'
$LOAD_PATH.unshift '../entity'

require 'rexml/document'
require 'kconv'
require 'yaml'
require 'time'
require 'logger'
require 'utils'
include Utils
require 'cryption'

# ログファイルパス
LOG_PATH = "../log/log_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

# 一度に受信可能な対戦結果数
TRACK_RECORD_MAX_SIZE = 250

# 対戦のマッチング時にどれだけ離れた時間のタイムスタンプをマッチングOKとみなすか
MATCHING_TIME_LIMIT_SECONDS = 300

# HTTP/HTTPSレスポンス文字列
res_status = "Status: 500 Internal Server Error\n"
res_header = ''
res_body = ""

# ログ開始
log = Logger.new(LOG_PATH)
log.level = Logger::DEBUG
log_msg = "" # ログに出すメッセージ

if ENV['REQUEST_METHOD'] == 'POST' then
	begin
		track_records = []         # 今回DBにインサートした対戦記録
		source_track_records = []  # 受信対戦記録
		insert_records_count = 0   # 登録件数
		matched_records_count = 0    # マッチング成功件数
		is_force_insert = false      # 強制インサートモード設定（同一アカウントからの重複時にエラー終了せず続行する）
		PLEASE_RETRY_FORCE_INSERT = "<Please Retry in Force-Insert Mode>"  # 強制インサートリトライのお願い文字列
		
		# 受信XMLデータをパース
		source = STDIN.read(ENV['CONTENT_LENGTH'].to_i)
		xml_data = REXML::Document.new(source)
		data = xml_data.elements['/trackrecordPosting']
		source_track_records = data.elements.each('game/trackrecord') do end
		game_id = data.elements['game/id'].text.to_i
		
		# DB 接続
		require 'db'
		db = DB.getInstance
		
		# アカウント認証
		# 認証失敗時は例外が投げられる
		require 'authentication'
		begin
			account = Authentication.login(data.elements['account/name'].text, data.elements['account/password'].text)
		rescue => ex
			res_status = "Status: 401 Unauthorized\n"
			res_body = "アカウント認証エラーです。\n"
			raise ex
		end
		
		# バリデーション
		if (source_track_records.size > TRACK_RECORD_MAX_SIZE) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "一度に受信できる対戦結果データ数は#{TRACK_RECORD_MAX_SIZE}件までです。\n"
			raise "データ件数が多すぎます。"
		elsif (source_track_records.size <= 0)
			res_status = "Status: 400 Bad Request\n"
			res_body = "送信された対戦結果データ数が0件です。\n"
			raise "受信報告データなし。"
		end
		
		# インサートモード設定
		if (data.elements['is_force_insert'] && data.elements['is_force_insert'].text && data.elements['is_force_insert'].text.to_s == 'true')
			is_force_insert = true
		else
			is_force_insert = false
		end
		
		# ログ記録
		log_msg = "#{source_track_records.length} rcv.\t#{is_force_insert.to_s}\t#{data.elements['account/name'].text}" if data.elements['account/name'].text and source_track_records
		log_msg << "\t#{Time.now - now}"
				
		# トランザクション開始
		db.exec("BEGIN TRANSACTION;")
		
		# 強制インサートモード時
		# DBにある同一アカウントの既存データを、あらかじめ受信データから取り除く	
		if is_force_insert then
			res_body = "強制インサートモードで実行します。\n" 
			res_body << "報告データ中に、同一アカウント・同一タイムスタンプの既存データがあっても、エラー終了せず続行します。\n"
			res_body << "\n"
			begin
				existing_timestamps = [] # 既存データの対戦タイムスタンプ
				
				# 既存の同一アカウントの対戦結果タイムスタンプを取得
				res = db.exec(<<-"SQL")
				  SELECT play_timestamp
				  FROM
				    track_records
				  WHERE
				    game_id = #{game_id.to_i}
					AND player1_account_id = #{account.id.to_i}
				SQL
				
				# 既存データの対戦タイムスタンプと同一タイムスタンプの報告データを削除
				res.each do |r|
					existing_timestamps << r[0]
				end
				
				res_body << "受信対戦結果データ件数：#{source_track_records.length.to_s}件\n"
				source_track_records.delete_if do |t|
					# タイムスタンプの文字列形式は、postgres モジュール以下レベルの実装依存
					existing_timestamps.index(iso8601_to_time(t.elements['timestamp'].text.to_s).strftime('%Y-%m-%d %H:%M:%S'))
				end
				res_body << "重複削除後対戦結果データ件数：#{source_track_records.length.to_s}件\n"
				
			rescue => ex
				res_status = "Status: 400 Bad Request\n"
				res_body << "同一アカウント・タイムスタンプで既にされている重複報告を、受信データから取り除く処理に失敗しました\n"
				raise ex
			else
				res_body << "同一アカウント・タイムスタンプで既にされている報告を、受信データから取り除きました。\n"
				res_body << "\n"
			end
		end
		
		res_body << "duplicated data delete finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG

		# 試合結果データをDBに登録する
		begin
			if source_track_records.length > 0 then
				require 'TrackRecord'
				
				# RETURNING付マルチプルINSERT用のSQL文生成
				source_track_records_insert_sql = <<-"SQL"
					INSERT INTO track_records (
						game_id,
						play_timestamp,
						player1_account_id,
						player1_name,
						player1_type1_id,
						player1_points,
						player2_name,
						player2_type1_id,
						player2_points,
						encrypted_base64_player2_name
					)
					VALUES
				SQL
				
				
				# VALUE 句生成
				source_track_records_values = []
				
				source_track_records.each do |t|
					# REXMLでXPATH使うと重いので、ハッシュに変換
					t_hash = {}
					t.each_child do |c|
						t_hash[c.name] = c.text
					end
					
					source_track_records_values << <<-"SQL"
						(
							#{game_id.to_i},
							to_timestamp('#{iso8601_to_time(t_hash['timestamp'].to_s).strftime("%Y-%m-%d %H-%M-%S")}', 'YYYY-MM-DD HH24-MI-SS'),
							#{account.id.to_i},
							#{s t_hash['p1name'].to_s},
							#{t_hash['p1type'].to_i},
							#{t_hash['p1point'].to_i},
							#{s t_hash['p2name'].to_s},
							#{t_hash['p2type'].to_i},
							#{t_hash['p2point'].to_i},
							#{s Cryption.encrypt_base64(t_hash['p2name'].to_s, account.data_password)}
						)
					SQL
				end
				
				source_track_records_insert_sql << source_track_records_values.join(",\n")
				source_track_records_insert_sql << " RETURNING *;"
				
				# インサート実行
				res = db.exec(source_track_records_insert_sql)
				
				# 結果取得
				res.each do |r|
					t = TrackRecord.new
					res.num_fields.times do |i|
						t.instance_variable_set("@#{res.fields[i]}", r[i])
					end
					track_records << t
				end
				res.clear
			end
		rescue => ex
			res_status = "Status: 400 Bad Request\n"
			res_body << "対戦結果の登録に失敗しました。\n"
			res_body << "すでに登録済みのデータが報告に含まれているかもしれません。\n"
			res_body << "\n"
			
			# 通常インサートのエラー時
			unless is_force_insert then
				res_body << "#{PLEASE_RETRY_FORCE_INSERT}\n"
				res_body << "強制インサートを使用すると、同一アカウント・同一タイムスタンプの既存データがあっても、無視して報告を続行できます。\n"
				res_body << "\n"
			end
			
			# 強制インサートのエラー時
			if is_force_insert then
				res_body << "強制インサート時でも、別アカウントから報告された、\n"
				res_body << "同一のタイムスタンプ・プレイヤー１の名前/使用キャラ・プレイヤー２の名前/使用キャラの\n"
				res_body << "データが既にある場合、アカウント重複防止のためエラーとなります。\n"
				res_body << "\n"
			end
			raise ex
		else
			res_body << "対戦結果の登録に成功しました（#{track_records.length}件登録しました）。\n"
		end
		
		insert_records_count = source_track_records.length
		
		# ログ記録
		log_msg = "#{insert_records_count} ins.\t" + log_msg if source_track_records

		log_msg << "\t#{Time.now - now}"
		
		res_body << "multiple insert finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		## インサートした対戦結果のマッチング
		
		# 試合タイムスタンプの昇順にソートして実施
		track_records.sort! { |a, b| a.play_timestamp <=> b.play_timestamp }
		
		begin
			require 'TrackRecord'
			# マッチ対象レコードの取得条件
			# 受信データのプレイヤー１のデータと既存データのプレイヤー２のデータが一致　かつ
			# 受信データのプレイヤー２のデータと既存データのプレイヤー１のデータが一致　かつ
			# 受信データと既存データのタイムスタンプが一定時間内　かつ
			# 受信データと既存データが別アカウントからの報告　かつ
			# 既存データがマッチング済みでない（受信データがマッチング済みでないのは自明）
				
			track_records.each do |t|

				res = db.exec(<<-"SQL")
				  SELECT
					*
				  FROM
					track_records
				  WHERE
					    player1_name = #{s t.player2_name.to_s}
					AND player1_type1_id = #{t.player2_type1_id.to_i}
					AND player1_points = #{t.player2_points.to_i}
					AND player2_name = #{s t.player1_name.to_s}
					AND player2_type1_id = #{t.player1_type1_id.to_i}
					AND player2_points = #{t.player1_points.to_i}
					AND play_timestamp <= to_timestamp(#{s t.play_timestamp.to_s}, \'YYYY-MM-DD HH24:MI:SS\') + interval\'#{MATCHING_TIME_LIMIT_SECONDS}\'
					AND play_timestamp >= to_timestamp(#{s t.play_timestamp.to_s}, \'YYYY-MM-DD HH24:MI:SS\') - interval\'#{MATCHING_TIME_LIMIT_SECONDS}\'
					AND player2_account_id IS NULL
					AND player1_account_id != #{t.player1_account_id.to_i}
				  ORDER BY
					play_timestamp
				  OFFSET 0 LIMIT 1
				SQL
				
				# もしマッチ対象レコードがあれば、受信データのレコード、マッチ対象のレコードについて、
				# お互いのプレイヤー２アカウントに、お互いのプレイヤー１アカウントを書き込み
				# また、お互いのマッチ対象対戦結果レコードカラムに書き込み
				if (res.num_tuples == 1) then
					matched_records_count += 1
					
					# マッチしたレコード情報を取得
					matched_record = TrackRecord.new
					res.num_fields.times do |i|
						matched_record.instance_variable_set("@#{res.fields[i]}", res[0][i])
					end
					
					# お互いのカラムを書き換え
					t_time = Time.parse(t.play_timestamp)
					matched_time = Time.parse(matched_record.play_timestamp)
					rep_timestamp = t_time + (matched_time - t_time) / 2
					
					# 受信対戦結果の更新
					updated_res = db.exec(<<-"SQL")
					  UPDATE
					    track_records
					  SET
					    player2_account_id = #{matched_record.player1_account_id.to_i},
					    matched_track_record_id = #{matched_record.id.to_i},
						rep_timestamp = to_timestamp(#{s rep_timestamp.strftime('%Y-%m-%d %H:%M:%S')}, \'YYYY-MM-DD HH24:MI:SS\'),
						updated_at = now(),
						lock_version = lock_version + 1
					  WHERE
					    id = #{t.id.to_i}
					    AND lock_version = #{t.lock_version.to_i}
					  RETURNING *
					SQL
					
					# 更新バージョン不一致時はやり直し
					redo if updated_res.num_tuples != 1
					updated_res.clear
					
					# マッチした対戦結果の更新
					updated_res = db.exec(<<-"SQL")
					  UPDATE
					    track_records
					  SET
					    player2_account_id = #{t.player1_account_id.to_i},
					    matched_track_record_id = #{t.id.to_i},
						rep_timestamp = to_timestamp(#{s rep_timestamp.strftime('%Y-%m-%d %H:%M:%S')}, \'YYYY-MM-DD HH24:MI:SS\'),
						updated_at = now(),
						lock_version = lock_version + 1
					  WHERE
					    id = #{matched_record.id.to_i}
					    AND lock_version = #{matched_record.lock_version.to_i}
					  RETURNING *
					SQL
					
					# 更新バージョン不一致時はやり直し
					redo if updated_res.num_tuples != 1
					updated_res.clear
				end
				res.clear
			end
		rescue => ex
			res_status = "Status: 400 Bad Request\n"
			res_body << "対戦結果マッチング時にエラーが発生しました。\n"
			raise ex
		else
			res_body << "既存の対戦結果とのマッチングを正常に実行しました（#{matched_records_count}件マッチングしました）。\n"
		end
		
		# ログ記録
		log_msg = "#{matched_records_count} mtch.\t" + log_msg if matched_records_count
		
		log_msg << "\t#{Time.now - now}"
		
		res_body << "matched records search finish...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# トランザクション終了
		db.exec("COMMIT;")
		res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
						
		# DB ANALYZE
		if (insert_records_count + matched_records_count * 4) / 500.0 > rand() then
			db.exec("VACUUM ANALYZE track_records;")
			res_body << "DB analyzed...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
			log_msg << "\t#{Time.now - now}"
		end
		
	rescue => ex
		res_status = "Status: 400 Bad Request\n" unless res_status
		res_body << "対戦結果の登録・マッチング時にエラーが発生しました。ごめんなさい。（#{now.strftime('%Y/%m/%d %H:%M:%S')}）\n"
		File.open(ERROR_LOG_PATH, 'a') do |err_log|
			err_log.puts "#{now.strftime('%Y/%m/%d %H:%M:%S')} #{File::basename(__FILE__)} Rev.#{REVISION}" 
			err_log.puts source
			err_log.puts ex.to_s
			err_log.puts ex.backtrace.join("\n").to_s
			err_log.puts
		end
	else
		res_status = "Status: 200 OK\n"
		res_body << "正常に登録・マッチングを実行しました。報告ありがとうございます。\n"
	ensure
		# DB接続を閉じる
		db.close if db
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

# HTTP レスポンス送信
res_header = "content-type:text/plain; charset=utf-8\n"
print res_status
print res_header
print "\n"
print res_body

# ログ記録
begin
	times = Process.times
	log.debug(
		[
			File::basename(__FILE__),
			REVISION,
			Time.now - now,
			times.utime + times.stime,
			times.utime,
			times.stime,
			times.cutime,
			times.cstime,
			ENV['QUERY_STRING'].gsub(/\r\n|\n/, '\n')[0..99],
			log_msg
		].join("\t")
	)
rescue
end

exit
