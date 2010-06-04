#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now

	### 対戦結果I/F API ###
	REVISION = 'R0.35'
	DEBUG = false

	$LOAD_PATH.unshift '../common'
	$LOAD_PATH.unshift '../entity'
	$LOAD_PATH.unshift '../dao'

	require 'rexml/document'
	require 'kconv'
	require 'yaml'
	require 'time'
	require 'logger'
	require 'base64'
	
	require 'utils'
	require 'cryption'
	require 'cache'

	require 'TrackRecordDao'
	
	# ログファイルパス
	LOG_PATH = "../log/log_#{now.strftime('%Y%m%d')}.log"
	ACCESS_LOG_PATH = "../log/access_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "../log/error_#{now.strftime('%Y%m%d')}.log"

	# マッチ済み対戦結果トランザクションファイルディレクトリ
	TRN_DATA_DIR = "../dat/matched_track_records_trn"

	# 一度に受信可能な対戦結果数
	TRACK_RECORD_MAX_SIZE = 250

	# 受け入れ最大受信バイト数
	MAX_CONTENT_LENGTH = 1024 * TRACK_RECORD_MAX_SIZE

	# 対戦のマッチング時にどれだけ離れた時間のタイムスタンプをマッチングOKとみなすか
	MATCHING_TIME_LIMIT_SECONDS = 300

	# バリデーション用定数
	ID_REGEX = /\A[0-9]+\z/
	ACCOUNT_NAME_REGEX = /\A[a-zA-Z0-9_]+\z/
	ACCOUNT_PASSWORD_REGEX = /\A[\x01-\x7F]+\z/
			
	# HTTP/HTTPSレスポンス文字列
	res_status = "Status: 500 Internal Server Error\n"
	res_header = ''
	res_body = ""

	# ログ開始
	log = Logger.new(LOG_PATH)
	log.level = Logger::DEBUG
	log_msg = "" # ログに出すメッセージ

	# アクセスログ記録
	access_logger = Logger.new(ACCESS_LOG_PATH)
	access_logger.level = Logger::DEBUG
	access_logger.info(
		[
			"",
			now.strftime('%Y/%m/%d %H:%M:%S'),
			ENV['REMOTE_ADDR'],
			ENV['HTTP_USER_AGENT'],
			ENV['REQUEST_URI'],
			File::basename(__FILE__)
		].join("\t")
	)
	
rescue
	print "Status: 500 Internal Server Error\n"
	print "content-type: text/plain\n\n"
	print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
	exit
end

if ENV['REQUEST_METHOD'] == 'POST' then
	begin
		source_length = ENV['CONTENT_LENGTH'].to_i # 受信バイト数
		track_records = []         # 今回DBにインサートした対戦記録
		source_track_records = []  # 受信対戦記録
		last_play_timestamp = nil # 最終対戦時刻
		is_force_insert = false      # 強制インサートモード設定（同一アカウントからの重複時にエラー終了せず続行する）
		PLEASE_RETRY_FORCE_INSERT = "<Please Retry in Force-Insert Mode>"  # 強制インサートリトライのお願い文字列
		matched_track_records_str = "" # マッチ済み対戦結果トランザクションデータ
		matched_track_records_trn_file = nil # マッチ済み対戦結果トランザクションファイルパス
		matched_track_records_trn_ok_file = nil # マッチ済み対戦結果トランザクションOKファイルパス
		
		records_count = 0   # 登録件数
		matched_records_count = 0   # マッチング成功件数
		matched_track_record_ids = []   # マッチングした対戦結果レコードid
		
		type1_summary = {}  # キャラ別サマリ
		                    # キー1：キャラID
		                    # キー2：:matched_count マッチした対戦数 :wins マッチ済勝利数 :loses マッチ済敗北数
		type1_vs_type1_summary = {} # キャラ対キャラ別サマリ
		                            # キー1：キャラID
		                            # キー2：対戦キャラID
		                            # キー3： :matched_count マッチした対戦数 :wins マッチ済勝利数 :loses マッチ済敗北数
		account_summary = {} # アカウント別サマリ
		                     # キー1：アカウントID
		                     # キー2： :matched_count マッチした対戦数 :wins マッチ済勝利数 :loses マッチ済敗北数
		account_type1_summary = {} # アカウントキャラ別サマリ
		                           # キー1：アカウントID
		                           # キー2：キャラID
		                           # キー3： :matched_count マッチした対戦数 :wins マッチ済勝利数 :loses マッチ済敗北数
		account_player_name_summary = {} # アカウントプレイヤー名別サマリ
		                           # キー1：アカウントID
		                           # キー2：プレイヤー名
		                           # キー3： :matched_count マッチした対戦数
		
		
		# コンテント長のバリデーション
		if source_length > MAX_CONTENT_LENGTH then
			res_status = "Status: 400 Bad Request\n"
			res_body = "送信されたデータサイズが大きすぎます。\n"
			raise "送信されたデータサイズが大きすぎます（#{source_length} > #{MAX_CONTENT_LENGTH}）。"
		end
		
		# 受信データ文字コードチェック
		source = STDIN.read(source_length)
		unless (Kconv.isutf8(source)) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "エラー：入力された文字コードがUTF8ではないようです"
			raise "input char code validation error."
		end
		
		# 受信XMLデータをパース
		xml_data = REXML::Document.new(source)
		data = xml_data.elements['/trackrecordPosting']
		game_data = data.elements['game'] # 複数の game_id を含むデータには未対応なので、一番最初の game タグのみ処理。残りは無視。
		game_id = game_data.elements['id'].text.to_i
		account_name = data.elements['account/name'].text
		account_password = data.elements['account/password'].text
		source_track_records = game_data.elements.each('trackrecord') do end
		
		# バリデーション
		unless (
			account_name and
			account_name =~ ACCOUNT_NAME_REGEX and
			account_password and
			account_password =~ ACCOUNT_PASSWORD_REGEX and
			game_id and
			game_id.to_s =~ ID_REGEX
		) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "入力データが正しくありません\ninput data validation error.\n"
			raise "input data validation error."
		end
		
		if (source_track_records.size > TRACK_RECORD_MAX_SIZE) then
			res_status = "Status: 400 Bad Request\n"
			res_body = "一度に受信できる対戦結果データ数は#{TRACK_RECORD_MAX_SIZE}件までです。\n"
			raise "データ件数が多すぎます（#{source_track_records.size} > #{TRACK_RECORD_MAX_SIZE}）。"
		elsif (source_track_records.size <= 0)
			res_status = "Status: 400 Bad Request\n"
			res_body = "送信された対戦結果データ数が0件です。\n"
			raise "受信報告データなし。"
		end
		
		# DB 接続
		require 'db'
		db = DB.getInstance
		# キャッシュ接続
		cache = Cache.instance
		
		# アカウント認証
		# 認証失敗時は例外が投げられる
		require 'authentication'
		begin
			account = Authentication.login(account_name, account_password)
		rescue => ex
			res_status = "Status: 401 Unauthorized\n"
			res_body = "アカウント認証エラーです。\n"
			raise ex
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
				  SELECT
				    play_timestamp
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
					existing_timestamps.index(Time.iso8601(t.elements['timestamp'].text.to_s).localtime.strftime('%Y-%m-%d %H:%M:%S'))
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
							to_timestamp('#{Time.iso8601(t_hash['timestamp'].to_s).localtime.strftime("%Y-%m-%d %H-%M-%S")}', 'YYYY-MM-DD HH24-MI-SS'),
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
		
		records_count = source_track_records.length
		
		# ログ記録
		log_msg = "#{records_count} ins.\t" + log_msg if source_track_records

		log_msg << "\t#{Time.now - now}"
		
		res_body << "multiple insert finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# 最終対戦時刻を作成or更新
		if track_records.length > 0 then
			last_play_timestamp = (track_records.map { |t| t.play_timestamp }).max

			begin
				res_update = db.exec(<<-"SQL")
				  UPDATE
					game_accounts
				  SET
					last_play_timestamp = to_timestamp(#{s last_play_timestamp.to_s}, \'YYYY-MM-DD HH24:MI:SS\')
				  WHERE
					game_id = #{game_id.to_i}
					AND account_id = #{account.id.to_i}
					AND (
					  last_play_timestamp < to_timestamp(#{s last_play_timestamp.to_s}, \'YYYY-MM-DD HH24:MI:SS\')
					  OR (last_play_timestamp IS NULL)
					)
				  RETURNING id
				SQL
				
				if res_update.num_tuples != 1 then
					res = db.exec(<<-"SQL")
					  INSERT INTO
						game_accounts
						(
						  account_id,
						  game_id,
						  rep_name,
						  last_play_timestamp
						)
					  VALUES
						(
						  #{account.id.to_i},
						  #{game_id.to_i},
						  #{s account.name},
						  to_timestamp(#{s last_play_timestamp.to_s}, \'YYYY-MM-DD HH24:MI:SS\')
						)
					SQL
					res.clear
				end
				res_update.clear
			
			rescue => ex
				res_status = "Status: 400 Bad Request\n"
				res_body << "最終対戦時刻登録時にエラーが発生しました。\n"
				raise ex
			else
				res_body << "最終対戦時刻登録時を正常に実行しました。\n" if DEBUG
			end
		end
			
		
		# キャラ別対戦数記録
		track_records.each do |t|
			type1_summary[t.player1_type1_id] ||= {}
			type1_summary[t.player1_type1_id][:count] ||= 0
			type1_summary[t.player1_type1_id][:count] += 1
		end
		
		### インサートした対戦結果のマッチング
		
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
						game_id = #{game_id.to_i}
					AND player1_name = #{s t.player2_name.to_s}
					AND player1_type1_id = #{t.player2_type1_id.to_i}
					AND player1_points = #{t.player2_points.to_i}
					AND player2_name = #{s t.player1_name.to_s}
					AND player2_type1_id = #{t.player1_type1_id.to_i}
					AND player2_points = #{t.player1_points.to_i}
					AND play_timestamp <= to_timestamp(#{s t.play_timestamp.to_s}, \'YYYY-MM-DD HH24:MI:SS\') + interval\'#{MATCHING_TIME_LIMIT_SECONDS}\'
					AND play_timestamp >= to_timestamp(#{s t.play_timestamp.to_s}, \'YYYY-MM-DD HH24:MI:SS\') - interval\'#{MATCHING_TIME_LIMIT_SECONDS}\'
					AND matched_track_record_id IS NULL
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
					
					# マッチしたレコードのidを記録
					matched_track_record_ids << t.id
					matched_track_record_ids << matched_record.id
					
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
					SQL
					
					# 更新バージョン不一致時はやり直し
					redo if updated_res.cmdstatus != 'UPDATE 1'
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
					SQL
					
					# 更新バージョン不一致時はやり直し
					redo if updated_res.cmdstatus != 'UPDATE 1'
					updated_res.clear
					
					# サマリ情報を変数に記録
					type1_summary[t.player1_type1_id] ||= {}
					type1_summary[t.player1_type1_id][:matched_count] ||= 0
					type1_summary[t.player1_type1_id][:wins] ||= 0
					type1_summary[t.player1_type1_id][:loses] ||= 0
					type1_summary[t.player1_type1_id][:matched_count] += 1
					type1_summary[t.player1_type1_id][:wins]  += ((t.player1_points.to_i <=> t.player2_points.to_i) + 1) / 2
					type1_summary[t.player1_type1_id][:loses] += ((t.player2_points.to_i <=> t.player1_points.to_i) + 1) / 2
					
					type1_summary[t.player2_type1_id] ||= {}
					type1_summary[t.player2_type1_id][:matched_count] ||= 0
					type1_summary[t.player2_type1_id][:wins]  ||= 0
					type1_summary[t.player2_type1_id][:loses] ||= 0
					type1_summary[t.player2_type1_id][:matched_count] += 1
					type1_summary[t.player2_type1_id][:wins]  += ((t.player2_points.to_i <=> t.player1_points.to_i) + 1) / 2
					type1_summary[t.player2_type1_id][:loses] += ((t.player1_points.to_i <=> t.player2_points.to_i) + 1) / 2
					
					type1_vs_type1_summary[t.player1_type1_id] ||= {}
					type1_vs_type1_summary[t.player1_type1_id][t.player2_type1_id] ||= {}
					type1_vs_type1_summary[t.player1_type1_id][t.player2_type1_id][:matched_count] ||= 0
					type1_vs_type1_summary[t.player1_type1_id][t.player2_type1_id][:wins]  ||= 0
					type1_vs_type1_summary[t.player1_type1_id][t.player2_type1_id][:loses] ||= 0
					type1_vs_type1_summary[t.player1_type1_id][t.player2_type1_id][:matched_count] += 1
					type1_vs_type1_summary[t.player1_type1_id][t.player2_type1_id][:wins]  += ((t.player1_points.to_i <=> t.player2_points.to_i) + 1) / 2
					type1_vs_type1_summary[t.player1_type1_id][t.player2_type1_id][:loses] += ((t.player2_points.to_i <=> t.player1_points.to_i) + 1) / 2
					
					type1_vs_type1_summary[t.player2_type1_id] ||= {}
					type1_vs_type1_summary[t.player2_type1_id][t.player1_type1_id] ||= {}
					type1_vs_type1_summary[t.player2_type1_id][t.player1_type1_id][:matched_count] ||= 0
					type1_vs_type1_summary[t.player2_type1_id][t.player1_type1_id][:wins]  ||= 0
					type1_vs_type1_summary[t.player2_type1_id][t.player1_type1_id][:loses] ||= 0
					type1_vs_type1_summary[t.player2_type1_id][t.player1_type1_id][:matched_count] += 1
					type1_vs_type1_summary[t.player2_type1_id][t.player1_type1_id][:wins]  += ((t.player2_points.to_i <=> t.player1_points.to_i) + 1) / 2
					type1_vs_type1_summary[t.player2_type1_id][t.player1_type1_id][:loses] += ((t.player1_points.to_i <=> t.player2_points.to_i) + 1) / 2
					
					account_summary[t.player1_account_id] ||= {}
					account_summary[t.player1_account_id][:matched_count] ||= 0
					account_summary[t.player1_account_id][:wins] ||= 0
					account_summary[t.player1_account_id][:loses] ||= 0
					account_summary[t.player1_account_id][:matched_count] += 1
					account_summary[t.player1_account_id][:wins]  += ((t.player1_points.to_i <=> t.player2_points.to_i) + 1) / 2
					account_summary[t.player1_account_id][:loses] += ((t.player2_points.to_i <=> t.player1_points.to_i) + 1) / 2
					
					account_summary[matched_record.player1_account_id] ||= {}
					account_summary[matched_record.player1_account_id][:matched_count] ||= 0
					account_summary[matched_record.player1_account_id][:wins] ||= 0
					account_summary[matched_record.player1_account_id][:loses] ||= 0
					account_summary[matched_record.player1_account_id][:matched_count] += 1
					account_summary[matched_record.player1_account_id][:wins]  += ((t.player2_points.to_i <=> t.player1_points.to_i) + 1) / 2
					account_summary[matched_record.player1_account_id][:loses] += ((t.player1_points.to_i <=> t.player2_points.to_i) + 1) / 2

					account_type1_summary[t.player1_account_id] ||= {}
					account_type1_summary[t.player1_account_id][t.player1_type1_id] ||= {}
					account_type1_summary[t.player1_account_id][t.player1_type1_id][:matched_count] ||= 0
					account_type1_summary[t.player1_account_id][t.player1_type1_id][:wins] ||= 0
					account_type1_summary[t.player1_account_id][t.player1_type1_id][:loses] ||= 0
					account_type1_summary[t.player1_account_id][t.player1_type1_id][:matched_count] += 1
					account_type1_summary[t.player1_account_id][t.player1_type1_id][:wins]  += ((t.player1_points.to_i <=> t.player2_points.to_i) + 1) / 2
					account_type1_summary[t.player1_account_id][t.player1_type1_id][:loses] += ((t.player2_points.to_i <=> t.player1_points.to_i) + 1) / 2
					
					account_type1_summary[matched_record.player1_account_id] ||= {}
					account_type1_summary[matched_record.player1_account_id][t.player2_type1_id] ||= {}
					account_type1_summary[matched_record.player1_account_id][t.player2_type1_id][:matched_count] ||= 0
					account_type1_summary[matched_record.player1_account_id][t.player2_type1_id][:wins] ||= 0
					account_type1_summary[matched_record.player1_account_id][t.player2_type1_id][:loses] ||= 0
					account_type1_summary[matched_record.player1_account_id][t.player2_type1_id][:matched_count] += 1
					account_type1_summary[matched_record.player1_account_id][t.player2_type1_id][:wins]  += ((t.player2_points.to_i <=> t.player1_points.to_i) + 1) / 2
					account_type1_summary[matched_record.player1_account_id][t.player2_type1_id][:loses] += ((t.player1_points.to_i <=> t.player2_points.to_i) + 1) / 2
					
					account_player_name_summary[t.player1_account_id] ||= {}
					account_player_name_summary[t.player1_account_id][t.player1_name] ||= {}
					account_player_name_summary[t.player1_account_id][t.player1_name][:matched_count] ||= 0
					account_player_name_summary[t.player1_account_id][t.player1_name][:matched_count] += 1
					
					account_player_name_summary[matched_record.player1_account_id] ||= {}
					account_player_name_summary[matched_record.player1_account_id][t.player2_name] ||= {}
					account_player_name_summary[matched_record.player1_account_id][t.player2_name][:matched_count] ||= 0
					account_player_name_summary[matched_record.player1_account_id][t.player2_name][:matched_count] += 1
	
					# マッチ済み対戦結果トランザクションデータ追加
					matched_track_records_str << "#{rep_timestamp.to_i},#{t.player1_account_id},#{matched_record.player1_account_id},#{t.player1_type1_id},#{t.player2_type1_id},#{t.player1_points},#{t.player2_points}\n"
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
		
		# ゲーム日次統計テーブルに書き込み
		begin
		
			# 更新または作成
			res_update = db.exec(<<-"SQL")
			  UPDATE
			    game_daily_stats
			  SET
			    track_records_count = track_records_count + #{records_count.to_i},
			    matched_track_records_count = matched_track_records_count + #{(matched_records_count * 2).to_i},
				updated_at = now(),
				lock_version = lock_version + 1
			  WHERE
			        game_id = #{game_id.to_i}
			    AND date_time = date_trunc('day', CURRENT_TIMESTAMP)
			  RETURNING id;
			SQL
							
			# UPDATE 失敗時は INSERT
			if res_update.num_tuples != 1 then
				res_update.clear
				res_insert = db.exec(<<-"SQL")
				  INSERT INTO
					game_daily_stats
					(
					  game_id,
					  date_time,
					  track_records_count,
					  matched_track_records_count
					)
				  VALUES
					(
					  #{game_id.to_i},
					  date_trunc('day', CURRENT_TIMESTAMP),
					  #{records_count.to_i},
					  #{(matched_records_count * 2).to_i}
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
		
		rescue => ex
			res_status = "Status: 400 Bad Request\n"
			res_body << "ゲーム日次統計テーブルの登録・更新時にエラーが発生しました\n"
			raise ex
		end
		
		res_body << "game_daily_stats udpate/insert finish...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# ゲームキャラ別日次統計テーブルに書き込み
		begin
			type1_summary.each do |type1_id, summary|
			
				# 更新または作成
				res_update = db.exec(<<-"SQL")
				  UPDATE
					game_type1_daily_stats
				  SET
					track_records_count = track_records_count + #{summary[:matched_count].to_i},
					wins = wins + #{summary[:wins].to_i},
					loses = loses + #{summary[:loses].to_i},
					updated_at = now(),
					lock_version = lock_version + 1
				  WHERE
						game_id = #{game_id.to_i}
					AND type1_id = #{type1_id.to_i}
					AND date_time = date_trunc('day', CURRENT_TIMESTAMP)
				  RETURNING id;
				SQL
								
				# UPDATE 失敗時は INSERT
				if res_update.num_tuples != 1 then
					res_update.clear
					res_insert = db.exec(<<-"SQL")
					  INSERT INTO
						game_type1_daily_stats
						(
						  game_id,
						  type1_id,
						  date_time,
						  track_records_count,
						  wins,
						  loses
						)
					  VALUES
						(
						  #{game_id.to_i},
						  #{type1_id.to_i},
						  date_trunc('day', CURRENT_TIMESTAMP),
						  #{summary[:matched_count].to_i},
						  #{summary[:wins].to_i},
						  #{summary[:loses].to_i}
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
			res_status = "Status: 400 Bad Request\n"
			res_body << "ゲームキャラ別日次統計テーブルの登録・更新時にエラーが発生しました\n"
			raise ex
		end
		
		res_body << "game_type1_daily_stats udpate/insert finish...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# ゲームキャラ対キャラ別日次統計テーブルに書き込み
		begin
			type1_vs_type1_summary.each do |type1_id, matched_type1_summary|
				matched_type1_summary.each do |matched_type1_id, summary|
				
					# 更新または作成
					res_update = db.exec(<<-"SQL")
					  UPDATE
						game_type1_vs_type1_daily_stats
					  SET
						track_records_count = track_records_count + #{summary[:matched_count].to_i},
						wins = wins + #{summary[:wins].to_i},
						loses = loses + #{summary[:loses].to_i},
						updated_at = now(),
						lock_version = lock_version + 1
					  WHERE
							game_id = #{game_id.to_i}
						AND type1_id = #{type1_id.to_i}
						AND matched_type1_id = #{matched_type1_id.to_i}
						AND date_time = date_trunc('day', CURRENT_TIMESTAMP)
					  RETURNING id;
					SQL
									
					# UPDATE 失敗時は INSERT
					if res_update.num_tuples != 1 then
						res_update.clear
						res_insert = db.exec(<<-"SQL")
						  INSERT INTO
							game_type1_vs_type1_daily_stats
							(
							  game_id,
							  type1_id,
							  matched_type1_id,
							  date_time,
							  track_records_count,
							  wins,
							  loses
							)
						  VALUES
							(
							  #{game_id.to_i},
							  #{type1_id.to_i},
							  #{matched_type1_id.to_i},
							  date_trunc('day', CURRENT_TIMESTAMP),
							  #{summary[:matched_count].to_i},
							  #{summary[:wins].to_i},
							  #{summary[:loses].to_i}
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
			end
		
		rescue => ex
			res_status = "Status: 400 Bad Request\n"
			res_body << "ゲームキャラ対キャラ別日次統計テーブルの登録・更新時にエラーが発生しました\n"
			raise ex
		end
		
		res_body << "game_type1_vs_type1_daily_stats udpate/insert finish...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# ゲームアカウント日次統計テーブルに書き込み
		begin
			account_summary.each do |account_id, summary|
			
				# 更新または作成
				res_update = db.exec(<<-"SQL")
				  UPDATE
					game_account_daily_stats
				  SET
					track_records_count = track_records_count + #{summary[:matched_count].to_i},
					wins = wins + #{summary[:wins].to_i},
					loses = loses + #{summary[:loses].to_i},
					updated_at = now(),
					lock_version = lock_version + 1
				  WHERE
						game_id = #{game_id.to_i}
					AND account_id = #{account_id.to_i}
					AND date_time = date_trunc('day', CURRENT_TIMESTAMP)
				  RETURNING id;
				SQL
								
				# UPDATE 失敗時は INSERT
				if res_update.num_tuples != 1 then
					res_update.clear
					res_insert = db.exec(<<-"SQL")
					  INSERT INTO
						game_account_daily_stats
						(
						  game_id,
						  account_id,
						  date_time,
						  track_records_count,
						  wins,
						  loses
						)
					  VALUES
						(
						  #{game_id.to_i},
						  #{account_id.to_i},
						  date_trunc('day', CURRENT_TIMESTAMP),
						  #{summary[:matched_count].to_i},
						  #{summary[:wins].to_i},
						  #{summary[:loses].to_i}
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
			res_status = "Status: 400 Bad Request\n"
			res_body << "ゲームアカウント日次統計テーブルの登録・更新時にエラーが発生しました\n"
			raise ex
		end
		
		res_body << "game_account_daily_stats udpate/insert finish...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
		# ゲームアカウントキャラ別日次統計テーブルに書き込み
		begin
			account_type1_summary.each do |account_id, t1_summary|
				t1_summary.each do |type1_id, summary|
					# 更新または作成
					res_update = db.exec(<<-"SQL")
					  UPDATE
						game_account_type1_daily_stats
					  SET
						track_records_count = track_records_count + #{summary[:matched_count].to_i},
						wins = wins + #{summary[:wins].to_i},
						loses = loses + #{summary[:loses].to_i},
						updated_at = now(),
						lock_version = lock_version + 1
					  WHERE
							game_id = #{game_id.to_i}
						AND account_id = #{account_id.to_i}
						AND type1_id = #{type1_id.to_i}
						AND date_time = date_trunc('day', CURRENT_TIMESTAMP)
					  RETURNING id;
					SQL
									
					# UPDATE 失敗時は INSERT
					if res_update.num_tuples != 1 then
						res_update.clear
						res_insert = db.exec(<<-"SQL")
						  INSERT INTO
							game_account_type1_daily_stats
							(
							  game_id,
							  account_id,
							  type1_id,
							  date_time,
							  track_records_count,
							  wins,
							  loses
							)
						  VALUES
							(
							  #{game_id.to_i},
							  #{account_id.to_i},
							  #{type1_id.to_i},
							  date_trunc('day', CURRENT_TIMESTAMP),
							  #{summary[:matched_count].to_i},
							  #{summary[:wins].to_i},
							  #{summary[:loses].to_i}
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
			end
		
		rescue => ex
			res_status = "Status: 400 Bad Request\n"
			res_body << "ゲームアカウントキャラ別日次統計テーブルの登録・更新時にエラーが発生しました\n"
			raise ex
		end
		
		res_body << "game_account_daily_stats udpate/insert finish...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
				
		# ゲームアカウントプレイヤー名日次統計テーブルに書き込み
		begin
			account_player_name_summary.each do |account_id, pn_summary|
				pn_summary.each do |player_name, summary|
					# 更新または作成
					res_update = db.exec(<<-"SQL")
					  UPDATE
						game_account_player_name_daily_stats
					  SET
						matched_track_records_count = matched_track_records_count + #{summary[:matched_count].to_i},
						updated_at = now(),
						lock_version = lock_version + 1
					  WHERE
							game_id = #{game_id.to_i}
						AND account_id = #{account_id.to_i}
						AND player_name = #{s player_name}
						AND date_time = date_trunc('day', CURRENT_TIMESTAMP)
					  RETURNING id;
					SQL
									
					# UPDATE 失敗時は INSERT
					if res_update.num_tuples != 1 then
						res_update.clear
						res_insert = db.exec(<<-"SQL")
						  INSERT INTO
							game_account_player_name_daily_stats
							(
							  game_id,
							  account_id,
							  player_name,
							  date_time,
							  matched_track_records_count
							)
						  VALUES
							(
							  #{game_id.to_i},
							  #{account_id.to_i},
							  #{s player_name},
							  date_trunc('day', CURRENT_TIMESTAMP),
							  #{summary[:matched_count].to_i}
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
			end
		
		rescue => ex
			res_status = "Status: 400 Bad Request\n"
			res_body << "ゲームアカウントプレイヤー名日次統計テーブルの登録・更新時にエラーが発生しました\n"
			raise ex
		end
		
		res_body << "game_account_player_name_daily_stats udpate/insert finish...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		

		# マッチ済み対戦結果トランザクションデータ追加書き込み
		matched_track_records_trn_file = "#{TRN_DATA_DIR}/#{game_id}_#{now.to_i}_#{$$}.dat"
		matched_track_records_trn_temp_file = "#{matched_track_records_trn_file}.temp"
		
		if (matched_track_records_str.length > 0) then
			log_msg << "\t#{matched_track_records_trn_file}"
	
			if (File.exist?(matched_track_records_trn_file) || File.exist?(matched_track_records_trn_temp_file)) then
				raise "エラー：マッチ済み対戦結果トランザクションデータファイル（#{matched_track_records_trn_file}）がすでに存在します"
			end
			
			File.open(matched_track_records_trn_temp_file, 'wb') do |w|
				w.print matched_track_records_str
			end
			File.rename(matched_track_records_trn_temp_file, matched_track_records_trn_file)
		end
			
		# キャッシュ更新
		if track_records.length > 0 then
			# ゲームアカウントごとの対戦結果idキャッシュ更新
			begin
				cache_key = "tr#{game_id.to_i.to_s(36)}_#{account.id.to_i.to_s(36)}"
				cache_val = (track_records.map { |t| t.id.to_i }).pack('I*')
				cache.append(cache_key, cache_val)
			rescue Memcached::NotStored 
				res = db.exec(<<-"SQL")
					SELECT
					  id
					FROM
					  track_records
					WHERE
					  game_id = #{game_id.to_i}
					  AND player1_account_id = #{account.id.to_i}
					ORDER BY
					  id DESC
				SQL
				
				cache_val = (res.map { |r| r[0].to_i }).pack('I*')
				
				begin
					cache.add(cache_key, cache_val)
				rescue Memcached::NotStored
					cache.delete cache_key
				end
			end
			
			# マッチした対戦結果レコードのキャッシュ削除
			trd = TrackRecordDao.new
			trd.delete_by_ids matched_track_record_ids
		end
	
		# トランザクション終了
		db.exec("COMMIT;")
		res_body << "transaction finished...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
		
=begin
		if track_records.length > 0 then
			# 対戦相手名・キャラごとの対戦結果idキャッシュ更新
			track_records_by_p2name_p2type1 = {}
			
			track_records.each do |t|
				track_records_by_p2name_p2type1[[t.player2_name, t.player2_type1_id]] ||= []
				track_records_by_p2name_p2type1[[t.player2_name, t.player2_type1_id]]  << t
			end
			
			track_records_by_p2name_p2type1.each do |p2name_p2type1, trs|
				
				begin
					cache.append(
						["trgnt", game_id.to_s(36), Base64.encode64(p2name_p2type1[0]).gsub(/[=\n]/, ''), p2name_p2type1[1].to_i.to_s(36)].join("_"),
						(trs.map { |t| t.id.to_i }).pack('I*')
					)
				rescue Memcached::NotStored 
				end
			end
		end
=end

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
