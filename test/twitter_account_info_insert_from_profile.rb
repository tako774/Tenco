TOP_DIR = '..'

$LOAD_PATH.unshift "#{TOP_DIR}/common"

require 'db'
require 'utils'

require "#{TOP_DIR}/dao/AccountExServiceAccountDao"
require "#{TOP_DIR}/dao/ExServiceAccountDao"
require "#{TOP_DIR}/entity/ExServiceAccount"

db = DB.getInstance
aesa_dao = AccountExServiceAccountDao.new
esa_dao = ExServiceAccountDao.new
account_profiles = []

res = db.exec(<<-"SQL")
  SELECT
    account_id, uri
  FROM
    account_profiles
  WHERE
    profile_property_id = 14
SQL

res.num_tuples.times do |i|
  account_profiles << [res[i][0].to_i, twitter_screen_name_from_uri(res[i][1])]
end

puts "#{account_profiles.length} 件のアカウントプロフィールデータ取得"

account_profiles.each do |account_profile|
  if screen_name = account_profile[1] then
    account_id = account_profile[0]
    
    ex_service_account = nil
    account_ex_service_account = AccountExServiceAccount.new
    
    # 外部サービスアカウント情報のデータを取得、まだなければ登録
    unless ex_service_account = esa_dao.get_by_ex_service_name_account_key('twitter', screen_name) then
      ex_service_account = ExServiceAccount.new
      ex_service_account.ex_service_id = 1
      ex_service_account.account_key = screen_name
      ex_service_account.request_update_flag = 1
      ex_service_account = esa_dao.insert(ex_service_account)
    end
    
    # Tenco!アカウントのもつ外部サービスアカウント情報を登録
    account_ex_service_account.account_id = account_id
    account_ex_service_account.ex_service_account_id = ex_service_account.id
    aesa_dao.insert(account_ex_service_account)
  end
end


