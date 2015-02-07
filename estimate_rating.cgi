#!/usr/bin/ruby

begin
	# 開始時刻
	now = Time.now

	### レート推定  ###
	REVISION = '0.16'
	DEBUG = false

	$LOAD_PATH.unshift './common'
	$LOAD_PATH.unshift './dao'
	$LOAD_PATH.unshift './entity'

	require 'kconv'
	require 'yaml'
	require 'time'
	require 'logger'

	require 'db'
	require 'utils'
	require 'setting'
	require 'GameProfileUtil'
	require 'segment_const'
	require 'erubis'
	include Erubis::XmlHelper

	source = ""

	# 共通設定読み込み
	CFG = Setting.new
	# TOP ページ URL
	TOP_URL = CFG['top_url']
	# TOP ディレクトリパス
	TOP_DIR = '.'
	# ログファイルパス
	LOG_PATH = "#{TOP_DIR}/log/log_#{now.strftime('%Y%m%d')}.log"
	ACCESS_LOG_PATH = "#{TOP_DIR}/log/access_#{now.strftime('%Y%m%d')}.log"
	ERROR_LOG_PATH = "#{TOP_DIR}/log/error_#{now.strftime('%Y%m%d')}.log"
	# キャッシュフォルダパス
	CACHE_DIR = "#{TOP_DIR}/cache/#{File::basename(__FILE__)}"
	# キャッシュロックフォルダパス
	CACHE_LOCK_DIR = "#{TOP_DIR}/cache/lock/#{File::basename(__FILE__)}"
	# キャッシュをつかったかどうか
	is_cache_used = false
	# 最大受付POSTデータサイズ（byte）
	MAX_POST_DATA_BYTES = 10000;
	# バリデーション用定数
	ID_REGEX = /\A[0-9]+\z/
	# 最大プロファイル名数
	max_name_nums = 20
	
	# サービス開始時刻
	service_start_hour = 6
	# サービス終了時刻
	service_end_hour = 18
	# サービス中かどうか
	is_available = nil
	
	# ログ開始
	logger = Logger.new(LOG_PATH)
	logger.level = Logger::DEBUG

	# アクセスログ記録
	access_logger = Logger.new(ACCESS_LOG_PATH)
	access_logger.level = Logger::DEBUG
	access_logger.info(
		[
			"",
			now.strftime('%Y/%m/%d %H:%M:%S'),
			ENV['HTTP_X_FORWARDED_FOR'] || ENV['HTTP_X_REAL_IP'] || ENV['REMOTE_ADDR'],
			ENV['HTTP_USER_AGENT'],
			ENV['REQUEST_URI'],
			File::basename(__FILE__)
		].join("\t")
	)
	
		
	# HTTP/HTTPSレスポンス文字列
	res_status = ''
	res_header = ''
	res_body = ''

	res_body = "#{now.to_s} #{File::basename(__FILE__)} Rev.#{REVISION}\n" if DEBUG

rescue => ex
	print "Status: 500 Internal Server Error\n"
	print "content-type: text/plain\n\n"
	print "サーバーエラーです。ごめんなさい。(Initialize Error #{Time.now.strftime('%Y/%m/%d %H:%m:%S')})"	
	exit
end



if ENV['REQUEST_METHOD'] == 'GET' then
	
	# サービス中かどうか判定
	case
	when service_end_hour < 24 then
		is_available = (service_start_hour <= now.hour and now.hour < service_end_hour)
	when service_end_hour >= 24 then
		is_available = (service_start_hour >= now.hour or now.hour < (service_end_hour - 24))
	else
		raise "failed to judge service availability."
	end
	
	if is_available then
		
		begin
			# クエリストリング
			query = {}
			# 推定対象の名前
			name = ""
			# 複数名分解後
			names = []
			# ゲームID
			game_id = 2 # デフォルト
			
			# ゲーム名
			game_name = ""
			# 対戦数
			track_record_counts = 0
			# type1 区分値
			type1 = {}
			# 推定結果
			estimations = nil
			
			# クエリストリング分解
			query = parse_query_str(ENV['QUERY_STRING'])
					
			# 入力バリデーション
			unless (
				(
					!query['game_id'] || query['game_id'] =~ ID_REGEX
				) and
				(
					!query['name'] || Kconv.isutf8(query['name'])
				)
			) then
				res_status = "Status: 400 Bad Request\n"
				res_body = "入力データが正しくありません\ninput data validation error.\n"
				raise "input data validation error."
			end
			
			
			# 名前が設定されていなければ推定
			if query['name'] and query['name'] != "" then
				names = query['name'].split(/<>/)
				names.delete_if { |str| str == "" }
				names.uniq!
				name = names.join(", ")
				if names.length > max_name_nums then
					res_body << "入力できるプロファイル名は#{max_name_nums}以下です\n"
					raise "入力できるプロファイル名は#{max_name_nums}以下です\n"
				end
				
				game_id = query['game_id'].to_i if query['game_id']
				
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
				
				res_body << "#{name} さんのレートを推定します\n"
				
				if res_game.num_tuples >= 1 then
					game_name = res_game[0][0]
					
					# レート推定
					estimations = GameProfileUtil.estimate_rating(names, game_id)
					
					if estimations.length > 0 then
						
						# 対戦結果数取得
						estimations.values.each do |est|
							track_record_counts += est[:track_record_counts]
						end
								
						res_body << "#{track_record_counts} 件の#{game_name}の対戦結果をレート計算対象として取得。\n"
						res_body << "matched trackrecords selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
												
						# Type1 区分値取得
						res = db.exec(<<-"SQL")
							SELECT
								type1_id, name
							FROM
								game_type1s
							WHERE
								game_id = #{game_id.to_i}
						SQL
						
						res.each do |r|
							type1[r[0].to_i] = r[1]
						end
						res.clear
						
						# 結果表示
						estimations.keys.sort.each do |type1_id|
							est = estimations[type1_id]
							if est[:rating] then
								res_body << "★#{name} さん（#{type1[type1_id]}）の推定レートは、#{est[:rating].to_i} ぐらいです\n"
							else
								res_body << "★#{name} さん（#{type1[type1_id]}）の推定レートは、対戦数が少ないため算出できませんでした\n"
							end
						end
						
						
						res_body << "------------------------------------------\n"
						res_body << "\n"
						estimations.keys.sort.each do |type1_id|
							est = estimations[type1_id]
							type1_log_likelihood = est[:log_likelihood]
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
	複数のプロファイル名を使用している場合は、「&lt;&gt;」で区切ってください（#{max_name_nums}個まで）。<br />
	</p>
	<form method="get" action="#{TOP_URL}estimate_rating.cgi" accept-charset="UTF-8">
		<label><input type="radio" name="game_id" value="1" #{"checked=\"checked\" " if game_id.to_i == 1}/>東方緋想天</label>
		<label><input type="radio" name="game_id" value="2" #{"checked=\"checked\" " if game_id.to_i == 2}/>東方非想天則</label>
		<label><input type="radio" name="game_id" value="4" #{"checked=\"checked\" " if game_id.to_i == 4}/>東方心綺楼</label><br />
		<input type="text" name="name" size="40" value="#{ h(names.join("<>")) if names }" />
		<input type="submit" value="推定" />
	</form>
	#{"<br />\n\t<hr />\n\t<pre>" + h(res_body) + "</pre>" if res_body != ''} 
	<p style="text-align:right;font-size:90%">
	レート推定の利用可能時間帯：#{service_start_hour}時から#{service_end_hour}時まで<br />
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
				log.puts ex.class.to_s
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
		res_status = "Status: 503 Service Temporary Unavailable\n" 
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
	複数のプロファイル名を使用している場合は、「&lt;&gt;」で区切ってください（#{max_name_nums}個まで）。<br />
	</p>
	<p>
		<strong>
			現在、レート推定は昼間（#{service_start_hour}時から#{service_end_hour}時まで）のみ利用可能です。<br />
			夜間から未明までは高負荷になるため、利用を制限しています。(2010/08/04)
		</strong>
	</p>
	<p class="suppli">
		おまけ：<a href="http://shindanmaker.com/40966" target="_blank">こんなの</a>できてました。(2010/08/19)
	</p>
	<p style="text-align:right;font-size:90%">
	レート推定の利用可能時間帯：#{service_start_hour}時から#{service_end_hour}時まで<br />
	リンク・アンリンクフリー
	</p>
</body>
</html>	
		HTML
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