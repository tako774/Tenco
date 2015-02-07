#!/usr/bin/ruby

### Pov 3:ゲーム別マッチング数ランキングの達成記録の保存 ###
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
  res_body << "Pov 3:ゲーム別マッチング数ランキング処理開始\n"

  # 設定
  pov_id = 3

  prizes = [] # 処理対象の prize
  is_prepared = false # PREPARE文を実行したかどうか
  
  # DB接続
  db = DB.getInstance
  # トランザクション開始
  db.exec("BEGIN TRANSACTION")
  
  res_body << "DB connected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
    
  # 処理対象の prize の取得
  require 'Prize'
  res = db.exec(<<-"SQL")
    SELECT
      p.id, p.game_id
    FROM
      prizes p,
      games g
    WHERE
          p.pov_id = #{pov_id.to_i}
      AND p.game_id = g.id
      AND g.is_batch_target = 1
    ORDER BY
      g.id
  SQL
  
  res.each do |r|
    p = Prize.new
    p.id = r[0].to_i
    p.game_id = r[1].to_i
    prizes << p
  end
  res.clear
  
  res_body << "Prizes selected...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
  res_body << "\n" if DEBUG
  
  # prize ごとに処理
  prizes.each do |prize|
    prize_id = prize.id
    game_id = prize.game_id
    
    res_body << "★Prize ID:#{prize_id} の処理\n"
    res_body << "Game ID:#{game_id}\n"
    
    # 変数
    prizes = [] # プライズ情報
    game_account_ratings = [] # マッチ済みアカウント数情報
    rank_member_count = 0  # ランキング対象キャラ総数
    class1_rank_limit = 200 # クラス１の値下限
    class2_rank_limit = 100 # クラス２の値下限
    class3_rank_limit = 50  # クラス３の値下限
    
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
    
    # 既存のプライズアカウント情報を取得
    prize_accounts = {}
    
    res = db.exec(<<-"SQL")
      SELECT 
        account_id,
        type1_id,
        pov_class_value
      FROM 
        prize_accounts pa
      WHERE
        pa.prize_id = #{prize_id.to_i}
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
      if !is_prepared then
        res_update = db.exec(<<-"SQL")
          PREPARE
            update_prize_accounts(int, int, int, int)
          AS
            UPDATE
              prize_accounts
            SET
              pov_class_value = $1,
              date_time =
                CASE pov_class_value
                  WHEN $1 THEN date_time
                  ELSE CURRENT_TIMESTAMP
                END,
              updated_at = CURRENT_TIMESTAMP,
              lock_version = lock_version + 1
            WHERE
                  prize_id = $2
              AND account_id = $3
              AND type1_id = $4
            RETURNING
              id
        SQL
        is_prepared = true
      end
      
      inserted_count = 0
      updated_count = 0
      skip_count = 0
      game_account_ratings.each do |gar|
        
        # 更新後のクラスを算出
        pov_class_value = nil
        matched_accounts = gar.matched_accounts.to_i
        
        case matched_accounts
        when 0 .. class3_rank_limit - 1
          pov_class_value = 0
        when class3_rank_limit .. (class2_rank_limit - 1)
          pov_class_value = POV_CLASS[:high_game_type1_ratings_ranker][:tertiary][:value]
        when class2_rank_limit .. (class1_rank_limit - 1)
          pov_class_value = POV_CLASS[:high_game_type1_ratings_ranker][:secondary][:value]
        else
          pov_class_value = POV_CLASS[:high_game_type1_ratings_ranker][:primary][:value]
        end
        
        # まだプライズアカウント情報レコードがなければ作成
        if !(prize_accounts[gar.account_id] &&
             prize_accounts[gar.account_id][gar.type1_id]) then
          db.exec(<<-"SQL")
            INSERT INTO
            prize_accounts
            (
              prize_id,
              account_id,
              type1_id,
              date_time,
              pov_class_value
            )
            SELECT
            #{prizes[0].id.to_i},
            #{gar.account_id.to_i},
            #{gar.type1_id.to_i},
            CURRENT_TIMESTAMP,
            #{pov_class_value.to_i}
            WHERE
            NOT EXISTS (
              SELECT
              *
              FROM
              prize_accounts
              WHERE
              prize_id = #{prize_id.to_i}
              AND account_id = #{gar.account_id.to_i}
              AND type1_id = #{gar.type1_id.to_i}
            )
          SQL
          inserted_count += 1
        # クラスが変わっていれば更新
        elsif prize_accounts[gar.account_id][gar.type1_id].to_i != pov_class_value.to_i then
          res_update = db.exec(<<-"SQL")
            EXECUTE update_prize_accounts(#{pov_class_value.to_i}, #{prize_id}, #{gar.account_id}, #{gar.type1_id})
          SQL
          
          if res_update.num_tuples != 1 then
            raise "PrizeAccount テーブルのアップデート対象がありませんでした：#{prize_id}, #{gar.account_id}, #{gar.type1_id}"
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
      res_body << "Prize ID:#{prize_id} プライズ達成情報保存時にエラーが発生しました。\n"
      raise ex
    else
      res_body << "Prize ID:#{prize_id} プライズ達成情報保存を正常に実行しました。\n"
    end
    
    res_body << "Prize ID:#{prize_id} prize status stored...(#{Time.now - now}/#{Process.times.utime}/#{Process.times.stime})\n" if DEBUG
    res_body << "\n" if DEBUG
  
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
