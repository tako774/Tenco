#!/usr/bin/ruby

# 開始時刻
now = Time.now
# リビジョン
REVISION = 'R0.40'
DEBUG = false

$LOAD_PATH.unshift './common'
$LOAD_PATH.unshift './entity'

require 'time'
require 'logger'
require 'segment_const'

# TOP ページ URL
TOP_URL = 'http://tenco.xrea.jp/'
# ログファイルパス
LOG_PATH = "./log/log_#{now.strftime('%Y%m%d')}.log"
ERROR_LOG_PATH = "./log/error_#{now.strftime('%Y%m%d')}.log"
# キャッシュフォルダパス
CACHE_DIR = "./cache/#{File::basename(__FILE__)}"
# キャッシュロックフォルダパス
CACHE_LOCK_DIR = "./cache/lock/#{File::basename(__FILE__)}"
# キャッシュをつかったかどうか
is_cache_used = false

# HTTP/HTTPSレスポンス文字列
res_status = "Status: 500 Server Error\n"
res_header = "content-type:text/plain; charset=utf-8\n"
res_body = ""

# ログ開始
logger = Logger.new(LOG_PATH)
logger.level = Logger::DEBUG

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		query = {} # クエリストリング
		db = nil   # DB接続 
		
		track_records = []  # 対戦結果
		type1 = {}          # プレイヤー属性１区分値
		type1_h = {}        # プレイヤー属性１区分値（HTML エスケープ済み）
		ratings = []         # プレイヤーのレーティング 
		matched_game_accounts = [] # 対戦相手情報
		account = nil # 対象アカウントの情報
		
		LINK_ERB_PATH   = "./link.erb"   # リンクERBパス
		FOOTER_ERB_PATH = "./footer.erb" # フッターERBパス
		
		# クエリストリング分解
		ENV['QUERY_STRING'].to_s.split(/[;&]/).each do |q|
		  key, val = q.split(/=/, 2)
		  query[key] = val.gsub(/\+/," ").gsub(/%[a-fA-F\d]{2}/){ $&[1,2].hex.chr } if val
		end
		
		if (query['game_id'] and query['game_id'] !='' and query['account_name'] and query['account_name'] != '') then
			account_name = query['account_name']  # アカウント名
			game_id = query['game_id'].to_i       # ゲーム番号
			output = query['output'] || 'html'    # 出力形式
			
			
			# キャッシュフォルダがなければ生成
			Dir.mkdir(CACHE_DIR, 0700) unless File.exist?(CACHE_DIR)
			Dir.mkdir(CACHE_LOCK_DIR, 0700) unless File.exist?(CACHE_LOCK_DIR)

			# キャッシュパス設定・プロセスロックファイルパス設定
			cache_xml_path  = "#{CACHE_DIR}/#{game_id.to_s}-#{account_name}.xml"
			cache_xml_header_path  = "#{cache_xml_path}.h"
			cache_html_path = "#{CACHE_DIR}/#{game_id.to_s}-#{account_name}.html"
			cache_html_header_path = "#{cache_html_path}.h"
			cache_lock_path = "#{CACHE_LOCK_DIR}/#{game_id.to_s}-#{account_name}.lock"
			
			# キャッシュパスのバリデーション
			if cache_xml_path =~ /\.{2}/ or cache_html_path =~ /\.{2}/ or cache_lock_path =~ /\.{2}/ then
				raise "ディレクトリトラバーサルの疑いがあります"
			end
			
			# デバッグ時か、キャッシュが無いかあってもサイズ0か、
			# ロックファイルが無いか、（＝キャッシュの再生成を行う条件）、キャッシュ生成
			unless (!DEBUG and
				File.exist?(cache_html_path) and (File.size(cache_html_path) != 0) and
				File.exist?(cache_html_header_path) and (File.size(cache_html_header_path) != 0) and
				File.exist?(cache_xml_path) and (File.size(cache_xml_path) != 0) and
				File.exist?(cache_xml_header_path) and (File.size(cache_xml_header_path) != 0) and
				File.exist?(cache_lock_path)
			) then			
				### キャッシュ生成
				# 生成プロセスをひとつだけにするために、プロセスロックする
				File.open(cache_lock_path, 'w') do |f|
					if f.flock(File::LOCK_EX | File::LOCK_NB) then	
						begin
							require 'db'
							require 'utils'
							include Utils
							require 'time'
							require 'erubis'
							include Erubis::XmlHelper
							
							# キャッシュの有効期限
							cache_expires = (now + 60 * 60) - now.min * 60 - now.sec
							
							# DB接続
							db = DB.getInstance
							
							# アカウント情報取得
							require 'Account'
							res = db.exec(<<-"SQL")
								SELECT
									id, name, data_password, show_ratings_flag
								FROM
									accounts
								WHERE
									name = #{s account_name}
									AND del_flag = 0
							SQL
							
							if res.num_tuples != 1 then
								res.clear
								res_status = "Status: 400 Bad Request\n"
								res_body = "該当アカウントは登録されていません\n"
								raise "該当アカウントは登録されていません"
							else
								account = Account.new
								res.num_fields.times do |i|
									account.instance_variable_set("@#{res.fields[i]}", res[0][i])
								end
								res.clear	
							end
							
							# ゲーム情報を取得
							require 'Game'
							res = db.exec(<<-"SQL")
								SELECT
									*
								FROM
									games
								WHERE
									id = #{game_id.to_i}
							SQL
							
							if res.num_tuples != 1 then
								res.clear
								res_status = "Status: 400 Bad Request\n"
								res_body = "ゲーム情報が登録されていません\n"
								raise "ゲーム情報が登録されていません"
							else
								game = Game.new
								res.num_fields.times do |i|
									game.instance_variable_set("@#{res.fields[i]}", res[0][i])
								end
								res.clear
							end
							
							# 該当アカウントのゲームごとの情報を取得
							require 'GameAccount'
							res = db.exec(<<-"SQL")
								SELECT
									ga.*,
									gc.name AS cluster_name
								FROM
									game_accounts ga
										LEFT OUTER JOIN 
											game_clusters gc
										ON
											gc.game_id = ga.game_id
											AND gc.cluster_id = ga.cluster_id
								WHERE
									ga.game_id = #{game_id.to_i}
									AND ga.account_id = #{account.id.to_i}
								SQL
							
							if res.num_tuples != 1 then
								game_account = GameAccount.new
								game_account.game_id = game_id.to_i
								game_account.account_id = game_id.to_i
								game_account.rep_name = account_name.to_s
								res.clear
								# res_status = "Status: 200 OK\n"
								# res_body = "このゲームでの対戦情報が未報告か、サーバーが未処理です。\n"
								# res_body << "すでに報告している場合には、申し訳ありませんが、少々お待ちください。\n"
								# raise "ゲーム・アカウント情報が未登録です"
							else
								game_account = GameAccount.new
								res.num_fields.times do |i|
									game_account.instance_variable_set("@#{res.fields[i]}", res[0][i])
								end
								res.clear
							end
							
							# NGワード伏字化
							game_account.rep_name = hide_ng_words(game_account.rep_name)
							
							# アカウントのレーティング情報を取得
							require 'GameAccountRating'
							res = db.exec(<<-"SQL")
								SELECT
								  r.*
								FROM
								  game_account_ratings r
								WHERE
								  r.game_id = #{game_id.to_i}
								  AND r.account_id = #{account.id.to_i}
								ORDER BY
								  r.ratings_deviation,
								  r.rating DESC
								SQL
							
							res.each do |r|
								rating = GameAccountRating.new
								res.num_fields.times do |i|
									rating.instance_variable_set("@#{res.fields[i]}", r[i])
								end
								ratings << rating
							end
							res.clear
							
							# アカウントの対戦記録を取得			
							# 未マッチの場合、player2 の名前は暗号化
							require 'TrackRecord'
							res = db.exec(<<-"SQL")
								SELECT
									t.play_timestamp,
									t.player1_name,
			  						t.player1_type1_id,
			  						t.player1_points,
									case
										when a2.name IS NULL then t.encrypted_base64_player2_name
										else t.player2_name
									end AS player2_name,
			  						t.player2_type1_id,
			  						t.player2_points,
									a2.name AS player2_account_name,
									ga.rep_name AS player2_rep_name,
									a2.del_flag AS player2_account_del_flag
								FROM
									track_records t
									LEFT OUTER JOIN
									(
									  accounts a2
									    LEFT OUTER JOIN
									      game_accounts ga
									    ON
									      ga.account_id = a2.id
										  AND ga.game_id = #{game_id.to_i}
									)
									ON
									  t.player2_account_id = a2.id
									  AND a2.del_flag = 0
								WHERE
									t.game_id = #{game_id.to_i}
									AND t.player1_account_id = #{account.id.to_i}
								ORDER BY
									t.play_timestamp DESC
								SQL
							
							res.each do |r|
								t = TrackRecord.new
								# 高速化のため変数名直接指定
								t.play_timestamp = r[0]
								t.player1_name = r[1]
								t.player1_type1_id = r[2]
								t.player1_points = r[3]
								t.player2_name = r[4]
								t.player2_type1_id = r[5]
								t.player2_points = r[6]
								t.player2_account_name = r[7]
								t.player2_rep_name = r[8]
								t.player2_account_del_flag = r[9]								
								#res.num_fields.times do |i|
								#	t.instance_variable_set("@#{res.fields[i]}", r[i])
								#end
								track_records << t
							end
							res.clear
							
							# NGワード伏字化
							track_records.each do |t|
								t.player1_name = hide_ng_words(t.player1_name)
								t.player2_name = hide_ng_words(t.player2_name)
							end
							
							# 対戦相手一覧作成
							require 'GameAccount'
							matched_game_accounts_names = {}
							track_records.each do |t|
								if (
									t.player2_account_name and
									t.player2_rep_name and
									!matched_game_accounts_names.key?(t.player2_account_name) and
									t.player2_account_del_flag.to_i == 0
								) then
									matched_game_account = GameAccount.new
									matched_game_account.account_name = t.player2_account_name.to_s
									matched_game_account.rep_name = t.player2_rep_name.to_s
									matched_game_accounts << matched_game_account
									matched_game_accounts_names[t.player2_account_name] = "1"
								end
							end
							matched_game_accounts_names = nil
							
							# Type1 区分値取得
							res = db.exec(<<-"SQL")
								SELECT
									segment_values.segment_value AS value, segment_values.name AS name
								FROM
									segment_values, games
								WHERE
									games.id = #{game_id.to_i}
								AND segment_values.segment_id = games.type1_segment_id
								SQL
							
							res.each do |r|
								type1[r[0].to_i] = r[1]
							end
							res.clear
							
							# 仮想 Type1 区分値取得
							SEG_V[:virtual_type1].each_value do |seg|
								type1[seg[:value].to_i] = seg[:name]
							end

							# 区分値を HTML エスケープしておく（h メソッドの呼び出し削減）
							type1.each do |k, v|
								type1_h[k] = h v
							end
							
						rescue => ex
							res_status = "Status: 500 Server Error\n"
							res_body << "サーバーエラーです。ごめんなさい。\n" unless res_body
							raise ex
						ensure
							db.close  if db
						end
						
						### キャッシュXML生成
						require 'rexml/document'
						
						# XML生成
						xml = REXML::Document.new
						xml << REXML::XMLDecl.new('1.0', 'UTF-8')
						
						# gameAccount 要素生成
						root = xml.add_element('gameAccount')
						
						# account 要素生成
						account_element = root.add_element('account')
						account_element.add_element('name').add_text(account_name)
						
						# game 要素生成
						game_element = account_element.add_element('game')
						game_element.add_element('id').add_text(game_id.to_s)
						game_element.add_element('name').add_text(game.name)
						
						if account.show_ratings_flag.to_i != 0 then
							# type1 要素生成
							ratings.each do |r|
								# ランダムを省く暫定対応
								unless r.type1_id.to_i == SEG_V[:virtual_type1][:random][:value].to_i
									type1_element = game_element.add_element('type1')
									type1_element.add_element('id').add_text(r.type1_id)
									type1_element.add_element('name').add_text(type1[r.type1_id.to_i])
									type1_element.add_element('elo_rating_value').add_text("#{r.rating.to_f.round.to_s}")
									type1_element.add_element('rating').add_text("#{r.rating.to_f.round.to_s}±#{r.ratings_deviation.to_f.floor.to_s}")
									type1_element.add_element('rating_value').add_text(r.rating.to_f.round.to_s)
									type1_element.add_element('ratings_deviation').add_text(r.ratings_deviation.to_f.floor.to_s)
									type1_element.add_element('matched_accounts').add_text(r.matched_accounts)
									type1_element.add_element('match_counts').add_text(r.match_counts)
								end
							end	
						end
						
						# キャッシュXML/ヘッダ出力
						File.open(cache_xml_path, 'w') do |w|
							w.flock(File::LOCK_EX)
							w.puts xml.to_s
							File.open(cache_xml_header_path, 'w') do |wh|
								wh.flock(File::LOCK_EX)
								wh.puts "Content-Type:text/xml; charset=utf-8"
								wh.puts "Last-Modified: #{now.httpdate}"
								wh.puts "Expires: #{cache_expires.httpdate}"
							end
						end
						
						### キャッシュHTML出力
						
						# リンク 部生成
						link_html = Erubis::Eruby.new(File.read(LINK_ERB_PATH)).result(binding)
						# footer 部生成
						footer_html = Erubis::Eruby.new(File.read(FOOTER_ERB_PATH)).result(binding)
						
						# キャッシュHTML/ヘッダ出力
						File.open(cache_html_path, 'w') do |w|
							w.flock(File::LOCK_EX)
							w.puts Erubis::Eruby.new(File.read("#{File::basename(__FILE__, '.*')}.erb")).result(binding)
							File.open(cache_html_header_path, 'w') do |wh|
								wh.flock(File::LOCK_EX)
								wh.puts "Content-Type:text/html; charset=utf-8"
								wh.puts "Last-Modified: #{now.httpdate}"
								wh.puts "Expires: #{cache_expires.httpdate}"
							end
						end

					else
						logger.info("Info: #{cache_lock_path} is locked.\n")
						is_cache_used = true
					end	# if f.flock(File::LOCK_EX | File::LOCK_NB) then	
				end # File.open(cache_lock_path, 'w') do |f|
			else
				is_cache_used = true
			end # unless (File.exist?(cache_html_path) and File.exist?(cache_xml_path)) then
			
			### 結果をセット
			if output == 'xml' then
				res_status = ""
				File.open(cache_xml_path, 'r') do |f|
					f.flock(File::LOCK_SH)
					res_body = f.read()
					File.open(cache_xml_header_path, 'r') do |fh|
						fh.flock(File::LOCK_SH)
						res_header = fh.read()
					end
				end
			else
				res_status = ""
				File.open(cache_html_path, 'r') do |f|
					f.flock(File::LOCK_SH)
					res_body = f.read()
					File.open(cache_html_header_path, 'r') do |fh|
						fh.flock(File::LOCK_SH)
						res_header = fh.read()
					end
				end
			end
		else
			res_status = "Status: 400 Bad Request\n"
			res_body = "400 Bad Request\n"
		end	
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
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

begin
# HTTP レスポンス送信
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
			ENV['QUERY_STRING']
		].join("\t")
	)
rescue
end

