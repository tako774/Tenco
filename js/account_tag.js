var got_account_tags=false; function get_account_tags(b){b=b;$("#account_tag_tool").hide();$("#account_tag_msg").text("\u6700\u65b0\u30bf\u30b0\u53d6\u5f97\u4e2d");$.ajax({type:"GET",url:"http://"+location.host+"/api/account_tag_select.cgi",data:{account_name:b},cache:false,dataType:"xml",success:function(a){a=$("account",$("account_tags",a));a=$("tag",a);$("#account_tags").empty();$("#account_tag_msg").text("\uff08\u6700\u65b0\u30bf\u30b0\u60c5\u5831\u53d6\u5f97\u6e08\u307f\uff09");a.each(function(){$("#account_tags").append('<li><a href="http://'+location.host+ "/tag/"+urlDecode2f(encodeURIComponent(xmlUnescape($("display_name",$(this)).text())))+'">'+$("display_name",$(this)).text()+"</a></li>")});$("#account_tag_tool").show();got_account_tags=true},error:function(){$("#account_tags").empty();$("#account_tag_msg").text("\u53d6\u5f97\u5931\u6557")}})} function add_account_tag(b,a){b=b;a=a;$("#account_tag_tool").hide();$("#account_tag_msg").text("\u767b\u9332\u4e2d");$.ajax({type:"POST",url:"http://"+location.host+"/api/account_tag.cgi",data:{account_name:b,tag_name:a},cache:true,success:function(c){c=document.createElement("li");var d=document.createElement("a");d.href="http://"+location.host+"/tag/"+urlDecode2f(encodeURIComponent(a));var e=document.createTextNode(a);d.appendChild(e);c.appendChild(d);$("#account_tags").append(c);$("#account_tag_msg").text("\u767b\u9332\u6210\u529f\uff08\u6b21\u56de\u306e\u30da\u30fc\u30b8\u66f4\u65b0\u5f8c\u304b\u3089\u3001\u767b\u9332\u3057\u305f\u30bf\u30b0\u304c\u8868\u793a\u3055\u308c\u307e\u3059\uff09")}, error:function(c){$("#account_tag_msg").text("\u767b\u9332\u5931\u6557\uff01\uff08"+getTimeStr(new Date)+"\uff09\n"+c.responseText)},complete:function(){$("#account_tag_tool").show()}})} function delete_account_tag(b,a){b=b;a=a;$("#account_tag_tool").hide();$("#account_tag_msg").text("\u524a\u9664\u4e2d");$.ajax({type:"POST",url:"http://"+location.host+"/api/account_tag_delete.cgi",data:{account_name:b,tag_name:a},cache:true,success:function(c){$("#account_tags > li").each(function(){$(this).text()==a&&$(this).remove()});$("#account_tag_msg").text("\u524a\u9664\u6210\u529f\uff08\u6b21\u56de\u306e\u30da\u30fc\u30b8\u66f4\u65b0\u5f8c\u304b\u3089\u3001\u524a\u9664\u3055\u308c\u305f\u30bf\u30b0\u304c\u898b\u3048\u306a\u304f\u306a\u308a\u307e\u3059\uff09")}, error:function(c){$("#account_tag_msg").text("\u524a\u9664\u5931\u6557\uff01\uff08"+getTimeStr(new Date)+"\uff09\n"+c.responseText)},complete:function(){$("#account_tag_tool").show()}})};