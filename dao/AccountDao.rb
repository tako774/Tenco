require "#{File.expand_path(File.dirname(__FILE__))}/DaoBase"
require "#{File.expand_path(File.dirname(__FILE__))}/../entity/Account"

class AccountDao < DaoBase
  @@version = 0.03

  # 指定されたアカウント名のアカウント情報を返す
  def get_account_by_name(account_name)
    account = nil
    
    res = @db.exec(<<-"SQL")
      SELECT
        id, name, data_password, show_ratings_flag
      FROM
        accounts
      WHERE
        name = #{s account_name}
        AND del_flag = 0
    SQL
    
    if res.num_tuples == 1 then
      account = Account.new
      res.num_fields.times do |i|
        account.instance_variable_set("@#{res.fields[i]}", res[0][i])
      end
    end
    
    res.clear
    
    return account
  end
  
end
