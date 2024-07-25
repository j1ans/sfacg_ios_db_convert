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
    
def get_db_value(field_name,table_name,condition): 
    print(f'{debug_log_time()}start get value[{field_name}] from table[{table_name}]')
    print(f'{debug_log_time()}checking parameter[{field_name}]') 
    list_db_value = [] 
    cursor.execute(f'SELECT {field_name} FROM {table_name} {condition} GROUP BY {field_name} ;')
    for value in cursor.fetchall():
        list_db_value.append(value[0])          
        print(f'{debug_log_time()}found {field_name}:{value[0]}')
    return list_db_value
    
def get_book_detail_from_url(book_id):
    print(f'{debug_log_time()}start get book[{book_id}] detail from sfacg')
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
    print(f'{debug_log_time()}successfully get bookid {book_id}title:{book_title}author:{book_author} from url')
    return book_title,book_author,book_desc

def process_volume(bookid,book_title,book_author,book_desc):
    print(f'{debug_log_time()}start process book[{bookid}]')
    volume_book_list = get_db_value('_id','Chapter',f'where bookId like {bookid}')  #获取书的卷ID
    for vol_id in volume_book_list: #遍历卷ID
        print(f'{debug_log_time()}start process volume[{vol_id}]')
        sno_volume = get_db_value('sno','Chapter',f'where _id like {vol_id}') #卷ID匹配有且仅有的一个值
        title_volume = get_db_value('title','Chapter',f'where _id like {vol_id}')
        output_epub(bookid,book_title,book_author,book_desc,int(sno_volume[0]),title_volume[0],vol_id)
        print(f'{debug_log_time()}finish output book[{bookid}]')   

def output_epub(book_id,book_title,book_author,book_desc,sno_volume,title_volume,id_volume):
    print(f'{debug_log_time()}start output epub {book_title}[{book_id}] volume{sno_volume} - {title_volume}')
    book = epub.EpubBook() #创建epub对象
    book.set_identifier(f"{book_id}_{id_volume}")
    book.set_title(f"{book_title} - 第 {sno_volume} 卷 - {title_volume}")
    book.set_language("zh")
    book.add_author(f"{book_author}")
    book.add_metadata('DC','description',f"{book_desc}")  
    first_loop = True
    cursor.execute(f"SELECT _id,title from Article where bookId like {book_id} AND chapterId like {id_volume}")#用Bookld和chapterId匹配每章的_id的标题
    for chapters in cursor.fetchall(): 
        cursor.execute(f"SELECT sno from ArticleContent where _id like {chapters[0]}") #直接用章节ID去匹配
        chapter_num = cursor.fetchone()
        if not chapter_num:
            print(f'{debug_log_time()}find NULL chapter [{chapters[0]}],skipping...')
            continue
        else:
            chapter_num = str_process(str(chapter_num))#去除(x),       
            cursor.execute(f"SELECT content from ArticleContent where _id like {chapters[0]}") #直接用章节ID去匹配
            chapter_content = cursor.fetchone()
            chapter_content = str(chapter_content[0])
            chapter_content = str_process(chapter_content)#去除(x),
            chapter_content = chapter_content.replace(u'\u3000',u' ').replace(u'\n','<br>')#去除unicode编码
            chapter_create_content =  epub.EpubHtml(title=f'{chapters[1]}',
                           file_name=f'chapter_{chapter_num}.xhtml',
                           lang='zh')
            chapter_create_content.set_content(f'<html><body><h1>{chapters[1]}</h1><p>{chapter_content}</p></body></html>') #生成章节
            book.add_item(chapter_create_content)
            if first_loop: #如果是第一次循环   
                spine = ['nav', chapter_create_content]
                toc = [epub.Link(f'chapter_{chapter_num}.xhtml', f'{chapters[1]}', f'{sno_volume}')  ]
                first_loop = False
            else:
                spine.append(chapter_create_content)
                # 创建章节的链接对象  
                chapter_link = epub.Link(f'chapter_{chapter_num}.xhtml', f'{chapters[1]}', f'{sno_volume}')  
                toc.append(chapter_link)  
  
    if not 'spine' in locals(): #判断是不是整个Book都是空
        print(f'{debug_log_time()}find NULL book [{chapters[0]}],skipping...')        
        return
    else:
        book.spine = spine
        # 最后，将目录列表设置为书籍的 TOC    
        book.toc = tuple(toc)  
  
        # 添加必要的 EPUB 文件  
        book.add_item(epub.EpubNcx())  
        book.add_item(epub.EpubNav())  
        epub.write_epub(f"{book_id}_{book_title}_{sno_volume}_{title_volume}.epub", book, {})
        print(f'{debug_log_time()}finish output volume {sno_volume}')    


    
def str_process(s):
    return s[1:-2] 
        
       
        
if __name__ == '__main__':
    con = sqlite3.connect('SFReader.Default.db') #打开菠萝包数据库
    cursor = con.cursor()
    list_db_books = get_db_value('bookId','Article','') #获取数据库有几本书
    for book in list_db_books:
        book_title,book_author,book_desc = get_book_detail_from_url(book)
        process_volume(book,book_title,book_author,book_desc)
                  
            
    con.commit()
    cursor.close()
    con.close()
