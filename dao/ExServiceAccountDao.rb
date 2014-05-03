require "#{File.expand_path(File.dirname(__FILE__))}/DaoBase"
require "#{File.expand_path(File.dirname(__FILE__))}/../entity/ExServiceAccount"

class ExServiceAccountDao < DaoBase
  @@version = 0.01
  EX_SERVICE_NAME_TWITTER = 'twitter'

  # 指定された外部サービス名・外部アカウントの情報を返す
  # なければ nil を返す
  def get_by_ex_service_name_account_key(ex_service_name, account_key)
    entity = ExServiceAccount.new
    
    res = @db.exec(<<-"SQL")
      SELECT
        esa.*
      FROM
        ex_service_accounts esa,
        ex_services es
      WHERE
            esa.ex_service_id = es.id
        AND es.name = #{s ex_service_name}
        AND esa.account_key = #{s account_key}
    SQL
    
    if res.num_tuples != 1 then
      return nil
    else
      res.num_fields.times do |i|
        entity.instance_variable_set("@#{res.fields[i]}", res[0][i])
      end
      return entity
    end
    
  end
  
  # 情報更新フラグが立っている外部サービスアカウントを取得
  def get_request_update_flag_on_by_ex_service_name(ex_service_name)
    entities = []
    
    res = @db.exec(<<-"SQL")
      SELECT
        esa.*
      FROM
        ex_service_accounts esa,
        ex_services es
      WHERE
            esa.ex_service_id = es.id
        AND es.name = #{s ex_service_name}
        AND request_update_flag = 1
    SQL
    
    res.each do |row|
      entity = ExServiceAccount.new
      res.num_fields.times do |i|
        entity.instance_variable_set("@#{res.fields[i]}", row[i])
      end
      entities << entity
    end
    
    return entities
  end
  
  # 指定されたアカウントIDたちの twitter 情報を返す
  def get_twitter_data_by_account_ids(account_ids)
    twitter_data = {}
    return twitter_data if account_ids.length == 0
    
    res = @db.exec(<<-"SQL")
      SELECT
        aesa.account_id,
        esa.account_key,
        esa.profile_image_url
      FROM
        account_ex_service_accounts aesa,
        ex_service_accounts esa,
        ex_services es
      WHERE
            aesa.account_id IN (#{(account_ids.map { |i| "'#{i.to_i}'" } ).join(", ")})
        AND aesa.ex_service_account_id = esa.id
        AND esa.ex_service_id = es.id
        AND es.name = #{s EX_SERVICE_NAME_TWITTER}
        AND esa.profile_image_url IS NOT NULL
    SQL
    
    res.each do |row|
      entity = {}
      
      account_id = row[0].to_i
      entity[:screen_name] = row[1]
      entity[:profile_image_url] = row[2] || ""
      
      entity[:url] = "http://twitter.com/#{entity[:screen_name]}/"
      entity[:icon_image_url] = entity[:profile_image_url].sub(/(\.[^.\/]+||)\z/, "_mini\\1")
      entity[:player_image_url] = entity[:profile_image_url].sub(/(\.[^.\/]+||)\z/, "_reasonably_small\\1")
      
      twitter_data[account_id] ||= []
      twitter_data[account_id] << entity
    end
    
    return twitter_data
  end
  
  # 外部サービスアカウント情報を登録
  def insert(ex_service_account)
    inserted_ex_service_account = ExServiceAccount.new
    
    res = @db.exec(<<-"SQL")
      INSERT INTO
        ex_service_accounts (
          ex_service_id
        , account_key
        #{", profile_image_url" if ex_service_account.profile_image_url}
        #{", request_update_flag" if ex_service_account.request_update_flag}
        )
      VALUES (
        #{ex_service_account.ex_service_id.to_i}
      , #{s ex_service_account.account_key}
      #{", #{s ex_service_account.profile_image_url}" if ex_service_account.profile_image_url}
      #{", #{ex_service_account.request_update_flag.to_i}" if ex_service_account.request_update_flag}
      )
      RETURNING
        *
    SQL
    
    res.num_fields.times do |i|
      inserted_ex_service_account.instance_variable_set("@#{res.fields[i]}", res[0][i])
    end
    
    return inserted_ex_service_account
  end
  
  # ID情報をキーとして外部サービスアカウント情報を更新する
  def update(ex_service_account)
    new_entity = nil
    
    raise "更新対象として渡されたエンティティのIDが nil です" if ex_service_account.id.nil?
    
    res = @db.exec(<<-"SQL")
      UPDATE
        ex_service_accounts
      SET
        #{"profile_image_url = #{s ex_service_account.profile_image_url} ," if ex_service_account.profile_image_url}
      #{"request_update_flag = #{ex_service_account.request_update_flag.to_i} ," if ex_service_account.request_update_flag}
        lock_version = lock_version + 1
      , updated_at = CURRENT_TIMESTAMP
      WHERE
        id = #{ex_service_account.id.to_i}
      RETURNING
        *
    SQL
    
    if res.num_tuples == 1 then
      new_entity = ExServiceAccount.new
      res.num_fields.times do |i|
        new_entity.instance_variable_set("@#{res.fields[i]}", res[0][i])
      end
    end
    
    return new_entity
  end
  
  # 指定されたアカウント名の更新要求フラグを立てる
  def set_request_flag_by_account_name(account_name)
  
    res = @db.exec(<<-"SQL")
      UPDATE
        ex_service_accounts
      SET
        request_update_flag = 1
      , lock_version = lock_version + 1
      , updated_at = CURRENT_TIMESTAMP
      WHERE
        id IN (
          SELECT
            esa.id
          FROM  
            accounts a,
            account_ex_service_accounts aesa,
            ex_service_accounts esa
          WHERE
                a.name = #{s account_name}
            AND aesa.account_id = a.id
            AND aesa.ex_service_account_id = esa.id
          )
    SQL
    
  end
  
end
