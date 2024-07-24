import sys,time
import sqlite3
import requests
from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub
import string
import re



def debug_log_time():
    date = time.strftime('[%H:%M:%S] ',time.localtime(time.time()))
    return date

def get_db_valve(field_name,table_name): 
    cursor.execute(f"SELECT {field_name} FROM {table_name} GROUP BY {field_name};")
    list_db_value = []
    for row in cursor.fetchall():
        list_db_value.append(row[0])
        print(debug_log_time() + "found " + field_name + f":{row[0]}")
    return list_db_value
        
def get_book_detail_from_url(book_id):
    url = (f"https://book.sfacg.com/novel/{book_id}")
    headers = { #设置请求头防止抓不到网页
        'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
        'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
   }
    response = requests.get(url,headers=headers)
    html_content = response.text # 拿到网页
    soup = BeautifulSoup(html_content,'html.parser')
    url_meta = description = soup.find("meta", attrs={"name": "keywords"})["content"] # 元数据内含 小说名,作者
    meta_list = url_meta.split(',')
    book_title = meta_list[0]
    book_author = meta_list[1]
    book_desc = (soup.find("p", attrs={"class": "introduce"})).get_text()
    print(debug_log_time() + f"successfully get bookid {book_id}" + " title:"+book_title+" author:"+book_author + " from url")
    return book_title,book_author,book_desc
    
def process_epub(book_title,book_author,book_id,book_desc):
    print(debug_log_time() + f"start process epub {book_id}" + " title:"+book_title+" author:"+book_author)
    cursor.execute(f"SELECT _id,sno,title from Chapter where bookId like {book_id}")
    for row in cursor.fetchall():
        print(debug_log_time() + f"start output volume{row[1]}")
        output_epub(book_title,book_author,book_id,remove_dot(str(row[1])),book_desc,row[0],row[2])
    print(debug_log_time() + f"finish output book!{book_id}")    
    
def output_epub(book_title,book_author,book_id,volume_num,book_desc,volume_id,volume_title):
    print(debug_log_time() + f"start output epub {book_id}" + " title:"+book_title+" author:"+book_author)  
    book = epub.EpubBook() #创建epub对象
    book.set_identifier(f"{book_id}_{volume_id}")
    book.set_title(f"{book_title} - 第 {volume_num} 卷 - {volume_title}")
    book.set_language("zh")
    book.add_author(f"{book_author}")
    book.add_metadata('DC','description',f"{book_desc}")
    cursor.execute(f"SELECT _id,title from Article where bookId like {book_id} AND chapterId like {volume_id}")    
    first_loop = True
    for chapters in cursor.fetchall():
        cursor.execute(f"SELECT sno from ArticleContent where _id like {chapters[0]}") #直接用章节ID去匹配
        chapter_num = cursor.fetchone()
        chapter_num = remove_db_str(str(chapter_num))
        cursor.execute(f"SELECT content from ArticleContent where _id like {chapters[0]}") #直接用章节ID去匹配   
        chapter_content = cursor.fetchone() 
        chapter_content = str(chapter_content[0])
        chapter_content = remove_db_str(chapter_content)
        chapter_content = chapter_content.replace(u'\u3000',u' ').replace(u'\n','<br>')
        chapter_list = []
        chapter_create_content =  epub.EpubHtml(title=f'{chapters[1]}',
                           file_name=f'chapter_{chapter_num}.xhtml',
                           lang='zh')
        chapter_create_content.set_content(f'<html><body><h1>{chapters[1]}</h1><p>{chapter_content}</p></body></html>') #生成章节
        book.add_item(chapter_create_content)
        if first_loop: #如果是第一次循环   
            spine = ['nav', chapter_create_content]
            toc = [epub.Link(f'chapter_{chapter_num}.xhtml', f'{chapters[1]}', f'{volume_num}')  ]
            first_loop = False
        else:
            spine.append(chapter_create_content)
            # 创建章节的链接对象  
            chapter_link = epub.Link(f'chapter_{chapter_num}.xhtml', f'{chapters[1]}', f'{volume_num}')  
            toc.append(chapter_link)  
  
    book.spine = spine
    # 最后，将目录列表设置为书籍的 TOC    
    book.toc = tuple(toc)  
  
    # 添加必要的 EPUB 文件  
    book.add_item(epub.EpubNcx())  
    book.add_item(epub.EpubNav())  
    epub.write_epub(f"{book_id}_{book_title}_{volume_num}_{volume_title}.epub", book, {})
    print(debug_log_time() + f"finish output volume {volume_num}")    
       

def remove_db_str(s):
    return s[1:-2]          

def remove_dot(s):
    return s[0:-2]     
       

con = sqlite3.connect('SFReader.Default.db') #打开菠萝包数据库
cursor = con.cursor()
list_db_books = []
list_db_books = get_db_valve("bookId","Article") #获取数据库有几本书
for item in list_db_books:
    book_title,book_author,book_desc = get_book_detail_from_url(item)
    process_epub(book_title,book_author,item,book_desc)
    
# 提交事务
con.commit()
 
# 关闭Cursor和Connection
cursor.close()
con.close()