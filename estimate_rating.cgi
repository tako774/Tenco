#!/usr/bin/ruby


begin
	# 開始時刻
	now = Time.now

	### レート推定  ###
	REVISION = '0.07'
	DEBUG = false

	$LOAD_PATH.unshift './common'
	$LOAD_PATH.unshift './entity'

	require 'kconv'
	require 'yaml'
	require 'time'
	require 'logger'

	require 'db'
	require 'utils'
	include Utils
	require 'segment_const'
	require 'erb'
	include ERB::Util

	source = ""

	# TOP ページ URL
	TOP_URL = 'http://tenco.xrea.jp/'
	# TOP ディレクトリパス
	TOP_DIR = '.'
	# ログファイルパス
	LOG_PATH = "#{TOP_DIR}/log/log_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "#{TOP_DIR}/log/error_#{now.strftime('%Y%m%d')}.log"
	# キャッシュフォルダパス
	CACHE_DIR = "#{TOP_DIR}/cache/#{File::basename(__FILE__)}"
	# キャッシュロックフォルダパス
	CACHE_LOCK_DIR = "#{TOP_DIR}/cache/lock/#{File::basename(__FILE__)}"
	# キャッシュをつかったかどうか
	is_cache_used = false
	# 最大受付POSTデータサイズ（byte）
	MAX_POST_DATA_BYTES = 10000;

	# ログ開始
	logger = Logger.new(LOG_PATH)
	logger.level = Logger::DEBUG
		
	# HTTP/HTTPSレスポンス文字列
	res_status = ''
	res_header = ''
	res_body = ''

	res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n" if DEBUG

rescue
	print "Status: 500 Internal Server Error\n"
	print "content-type: text/plain\n\n"
	print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"
end

if ENV['REQUEST_METHOD'] == 'GET' then
	begin
		# クエリストリング
		query = {}
		# 推定対象の名前
		name = ""
		# 複数名分解後
		names = []
		# ゲームID
		game_id = 1 # デフォルト
		# ゲーム名
		game_name = ""
		# レート候補
		rates = [900.0, 950.0, 1000.0, 1050.0, 1100.0, 1150.0, 1200.0, 1250.0, 1300.0, 1350.0, 1400.0, 1450.0, 1500.0, 1550.0, 1600.0, 1650.0, 1700.0, 1750.0, 1800.0, 1850.0, 1900.0, 1950.0, 2000.0, 2050.0, 2100.0, 2150.0, 2200.0, 2250.0, 2300.0, 2350.0, 2400.0]
		# レートごとの対数尤度
		log_likelihood = {}
		# 対戦結果
		track_records = [] 
		# type1 区分値
		type1 = {}
		
		# クエリストリング分解
		ENV['QUERY_STRING'].to_s.split(/[;&]/).each do |q|
			key, val = q.split(/=/, 2)
			query[key] = val.gsub(/\+/," ").gsub(/%[a-fA-F\d]{2}/){ $&[1,2].hex.chr } if val
		end
		
		
		# 名前が設定されていなければ推定
		if query['name'] and query['name'] != "" then
			names = query['name'].split(/<>/)
			names.delete_if { |str| str == "" }
			names.uniq!
			name = names.join(", ")
			if names.length > 10 then
				res_body << "入力できるプロファイル名は10以下です\n"
				raise "入力できるプロファイル名は10以下です\n"
			end
			
			game_id = query['game_id'].to_i if query['game_id']
			
			res_body << "#{name} さんのレートを推定します\n"
			
			# DB接続
			require 'db'
			db = DB.getInstance()
			db.exec("BEGIN TRANSACTION")
			
			res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
			
			# 対戦結果データ取得
			require 'Game'
			res_game = db.exec(<<-"SQL")
				SELECT
				  name
				FROM
				  games
				WHERE
				  id = #{game_id.to_i}
			SQL
			
			if res_game.num_tuples >= 1 then
				game_name = res_game[0][0]
			
				require 'TrackRecordRate'
				res = db.exec(<<-"SQL")
					SELECT
					  t.player1_points,
					  t.player2_points,
					  t.player2_type1_id,
					  gar.rating,
					  gar.ratings_deviation
					FROM
					  track_records t,
					  game_account_ratings gar
					WHERE
					  t.game_id = #{game_id.to_i}
					  AND gar.game_id = #{game_id.to_i}
					  AND t.player2_name in (#{(names.map { |n| s n }).join(", ")})
					  AND t.player1_account_id = gar.account_id
					  AND t.player1_type1_id = gar.type1_id
					  AND gar.ratings_deviation < 100
					SQL
					
				res.each do |r|
					t = TrackRecordRate.new
					# 高速化のためインスタンス名直接指定
					t.player1_points = r[0].to_i
					t.player2_points = r[1].to_i
					t.player2_type1_id = r[2].to_i
					t.rating = r[3].to_f
					t.ratings_deviation = r[4].to_f
#			res.num_fields.times do |i|
#				t.instance_variable_set("@#{res.fields[i]}", r[i])
#			end
					track_records << t
				end
				res.clear
						
				res_body << "#{track_records.length} 件の対戦結果をレート計算対象として取得。\n"
				res_body << "matched trackrecords selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
				
				# 対戦結果が取得できたときはレート推定
				if track_records.length > 0 then
											
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
								
					# 発生時間順にレート計算
					track_records.each do |t|
						
						# 対数尤度初期化
						unless log_likelihood[t.player2_type1_id]
							log_likelihood[t.player2_type1_id] = {}
							rates.each do |r|
								log_likelihood[t.player2_type1_id][r] = 0.0
							end
						end

						# Player2 取得ポイント
						point = (1.0 + (t.player2_points.to_i <=> t.player1_points.to_i)) * 0.5
						
						# レートごとの尤度計算
						rates.each do |r|
							# 期待勝率
							p_win = 1.0 / (1.0 + 10.0 ** ((t.rating - r) / 400.0))
							# 発生尤度加算
							if point == 1
								log_likelihood[t.player2_type1_id][r] += Math.log(p_win)
							elsif point == 0
								log_likelihood[t.player2_type1_id][r] += Math.log(1 - p_win)
							end
						end
						
					end
					
					res_body << "loglikelihood calculated...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
					
					# 結果表示
					log_likelihood.each do |type1_id, type1_log_likelihood|
						array = type1_log_likelihood.to_a.sort do |a, b|
							b[1] <=> a[1]
						end
						if array[0][1] <= -10
							res_body << "★#{name} さん（#{type1[type1_id]}）の推定レートは、#{array[0][0].to_i} ぐらいです\n"
						else
							res_body << "★#{name} さん（#{type1[type1_id]}）の推定レートは、対戦数が少ないため算出できませんでした\n"
						end
					end
					
					
					res_body << "------------------------------------------\n"
					res_body << "\n"
					log_likelihood.each do |type1_id, type1_log_likelihood|
					res_body << "参考：推定結果テーブル（#{type1[type1_id]}）\n"
						res_body << "レート\t対数尤度\n"
						array = type1_log_likelihood.to_a.sort do |a, b|
							b[1] <=> a[1]
						end
						array.each do |a|
							res_body << "#{a[0]}\t#{a[1]}\n"
						end
						res_body << "\n"
					end
					
				else
					res_body << "対戦結果は１件も取得できませんでした"
				end
			else
				res_body << "該当するゲームIDは登録されていません"
			end
			res_game.clear
		end

		# 出力
		res_header = "content-type: text/html; charset=utf-8\n"
		res_body = <<-"HTML"
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns='http://www.w3.org/1999/xhtml' xml:lang='ja' lang='ja'>
<head>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
	<title>Tenco! レート推定（仮）</title>
</head>
<body>
	<h1>Tenco! レート推定（仮）</h1>
	<p>
	入力されたゲーム内プロファイル名のレートを推定します。<br />
	Tenco! 未導入の方でも推定できます。精度はきっとかなり低いです。<br />
	半角カナは全角になおして入力してください。<br />
	複数のプロファイル名を使用している場合は、「&lt;&gt;」で区切ってください（10個まで）。<br />
	</p>
	<form method="get" action="http://tenco.xrea.jp/estimate_rating.cgi" accept-charset="UTF-8">
		<input type="text" name="name" id="name" size="40" />
		<input type="hidden" name="game_id" id="game_id" value="1" />
		<input type="submit" value="推定" />
	</form>
	#{"<br />\n\t<hr />\n\t<pre>" + h(res_body) + "</pre>" if res_body != ''} 
	<p style="text-align:right;font-size:90%">
	リンク・アンリンクフリー
	</p>
</body>
</html>	
		HTML
		
		
	rescue => ex
		res_status = "Status: 500 Server Error\n" unless res_status
		res_body << "レーティング推定時にエラーが発生しました。ごめんなさい。（#{now.to_s}）\n"
		File.open(ERROR_LOG_PATH, 'a') do |log|
			log.puts "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}"
			log.puts source
			log.puts ex.to_s
			log.puts ex.backtrace.join("\n").to_s
			log.puts
		end
	else
		res_status = "Status: 200 OK\n" unless res_status
	ensure
		# DB接続を閉じる
		db.close if db
	end
else
	res_status = "Status: 400 Bad Request\n"
	res_body = "400 Bad Request\n"
end

begin
# HTTP レスポンス送信
res_status "Status: 500 Internal Server Error\n" unless res_status
res_header = "content-type:text/plain; charset=utf-8\n" unless res_header
print res_status
print res_header
print "\n"
print res_body

# ログ記録
times = Process.times
res_body << "実行時間 #{Time.now - now}秒, CPU時間 #{times.utime + times.stime}秒" if DEBUG
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