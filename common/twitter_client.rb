# coding: utf-8
require 'rubygems'
require 'twitter'
require 'yaml'

class TwitterClient
  def self.get_instance
    config = YAML.load_file("#{File::dirname(__FILE__)}/../../../config/#{File.basename(__FILE__, '.*')}.yaml")
    return Twitter::Client.new(config)
  end
end
