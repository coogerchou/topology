import base64
import os
from flask import Flask, jsonify, render_template, request, send_file, render_template_string, session
import io
from diagrams import Diagram, Cluster, Edge, Node
from diagrams.custom import Custom
#from diagrams.aws.compute import EC2
from graphviz import Source
import pandas as pd
import numpy as np
from scour import scour
import logging

app = Flask(__name__, template_folder='templates', static_folder='static')
#app.secret_key = 'your_secret_key'  # 设置会话密钥


# 主页路由
@app.route('/')

#path_template = os.path.join('','custom_icon')

def home():
    app.logger.info('Index function is called')
    return render_template('index.html')  # 渲染前端页面

# 提交路由
@app.route('/submit', methods=['POST'])
def submit():
    data = request.json  # 获取前端提交的数据

    # 处理数据
    combinations = []
    for key, value in data.items():
        if key.startswith('product_'):
            index = key.split('_')[1]
            product = value
            location = data.get(f'location_{index}')
            combinations.append((product, location))
    print(combinations)

    # 生成图片
    png_data, svg_data = generate_images(combinations)

   # 返回结果
    return jsonify({
        'status': 'success',
        'png_image': base64.b64encode(png_data).decode('utf-8'),  # Base64 编码的 PNG 图片
        'svg_data': base64.b64encode(svg_data).decode('utf-8')   # Base64 编码的 SVG 图片
    })

# 你的生成图片函数
def generate_images(user_input):
    excel_path = os.path.join('data', 'topology-entry.xlsx')
    print(excel_path)

    def get_df(excel_path):
        
        #处理数据
        ##读取基础库
        df_mapping = pd.read_excel(excel_path, sheet_name='Product')
        df_mapping = df_mapping[df_mapping.columns[1:]]

        ##筛选必有的 node
        df_default = df_mapping[df_mapping['default'] == 'y']

        ##读取用户输入
        df_input_raw = pd.DataFrame(user_input,columns=['Product','Zone'])
        #df_input_raw = df_input_raw[df_input_raw.columns[1:]]

        ##把用户输入的内容，基于基础库 mapping 扩展
        df_input = pd.merge(df_input_raw, df_mapping[df_mapping.columns[:-2]], on='Product', how='left')
        df_input = pd.concat([df_input,df_default])

        ##整理选择用哪个 png
        df_input['icon-used'] = df_input[df_input['default'] != 'y']['icon-red']
        df_input['icon-used'][(df_input['default'] != 'y')&(df_input['Zone']=='业务应用区')] = df_input['icon-blue']

        df_input['icon-used'][df_input['default']=='y'] = df_input['icon-blue']

        list_special_product = [('EDR-red.png','电脑','desktop-EDR.png'), 
                                ('EDR-red.png','笔记本','laptop-EDR.png'),
                                ('HostEPP-red.png','服务器','server-EDR.png')]

        for special_product in list_special_product:
            if special_product[0] in df_input['icon-used'].to_list():
                df_input.loc[df_input['Product'] == special_product[1],'icon-used'] = special_product[2]
    
        return df_input
    
    df = get_df(excel_path)

    path_icon = os.path.join('static', 'custom_icon')

    global_node_attrs = {
        "fontsize": "11",  # 字体大小
        "width": "0.9",    # 节点宽度
        "height": "0.9",   # 节点高度
        "fixedsize": "true"  # 固定大小
    }

    graph_attrs = {
        "size": "12,12",  # 图表的最大尺寸 (宽度, 高度) 单位为英寸
        "dpi": "500",   # 每英寸点数，影响图像质量
        "ratio": "0.9",  # 自动调整比例以适应给定的 size
        "fontname": "Source Han Sans CN"
    }
    
    def draw_element(df, name_zone, is_visible='visible'):
        #print('--', name_zone, '--')
        df_temp = df[df['Zone']==name_zone]
        list_product = df_temp['Product'].to_list()
        list_icon_used = df_temp['icon-used'].to_list()
        
        df_temp_core = df_temp[df_temp['Core']=='y']
        if len(df_temp_core) > 0:
            #print(path_icon+df_temp_core['icon-used'])
            core = Custom(df_temp_core['Product'].to_list()[0], path_icon+'/'+df_temp_core['icon-used'].to_list()[0])
            core_product_name = df_temp_core['Product'].to_list()[0]
        else:
            core = ''
            core_product_name = ''
            
        products = []
        products_sub = []
        
        #把非 core 的生成对象，每 2 个一组
        for i in range(len(list_product)):
            #print("i", i)
            #print('list_product', list_product)
            #print('core', core_product_name)
            #print(list_product[i], list_icon_used[i])
            
            if list_product[i] != core_product_name: #
                #print('绘制') #
                products_sub.append(Custom(list_product[i], path_icon+'/'+list_icon_used[i])) #
            
            if (len(products_sub) == 2) or (i == len(list_product)-1): #
                products.append(products_sub) #
                products_sub = [] #

            #print('products', products)
            
        #print('len(products)', len(products))
        
        #把没有 core 的都连起来
        if core_product_name == '':
            for products_sub in products:
                for j in range(len(products_sub)):
                    #print("j", j)
                    if j > 0:
                        #print(is_visible)
                        if is_visible == 'visible':
                            products_sub[j] - products_sub[j-1]
                        else:
                            products_sub[j] - Edge(style="invis") - products_sub[j-1]
                            #print('虚线了')
            for l in range(len(products)):
                if l > 0:
                    products[j][-1] - Edge(style="invis") - products[j-1][0]
        
        #如果有 core，就把 core 和其他串联起来
        #if (core != '') and (is_visible == 'visible') and (name_zone == '交换区'):
        #    print('有 Core ！！！！', core, '但 visible')
        #    for products_sub in products:
        #        core - Edge(constraint='false') - products_sub
        if (core != '') and (is_visible != 'visible'):
            #print('有 Core ！！！！', core, '但 invisible')
            for products_sub in products:
                core - Edge(style = 'invis', constraint='false') - products_sub
        if (core != '') and (is_visible == 'visible'):
            for products_sub in products:
                core - Edge(constraint='false') - products_sub
        
        return core, products


    
    with Diagram('', show=False, filename=None, direction="LR", graph_attr=graph_attrs,\
                 node_attr=global_node_attrs, outformat=["png", "svg"]) as pic:

        with Cluster('互联网'):
            internet = draw_element(df, '互联网', is_visible='visible')[0]
        
        with Cluster('企业网络'):
            with Cluster('内部网络'):
                with Cluster('交换区'):
                    switch = draw_element(df, '交换区', is_visible='visible')[0]
            
                with Cluster('园区网'):
                    office = draw_element(df, '园区网', is_visible='invisible')[1]
                    for office_sub in office:
                        switch - office_sub
                
                with Cluster('数据中心'):
                    with Cluster('业务应用区'):
                        servers = draw_element(df, '业务应用区', is_visible='invisible')[1]
                        for servers_sub in servers:
                            switch - servers_sub
                        
                    
                    with Cluster('安全管理区'):
                        secs = draw_element(df, '安全管理区', is_visible='invisible')[1]
                        #switch - SOC
                        for secs_sub in secs:
                            switch - secs_sub
        
            with Cluster('网络周界'):
                    with Cluster('DMZ'):
                        firewall, DMZ = draw_element(df, 'DMZ', is_visible='invisible')
                        firewall - switch
                        for DMZ_sub in DMZ:
                            DMZ_sub - switch
        
        internet - Edge(style="dashed") - firewall
        
        # 获取生成的 DOT 源码
        dot_source = str(pic)
        dot_source = dot_source.replace(
            "digraph {",
            'digraph {\n    size="10,10";',  # 设置图像尺寸为 10x10 英寸
        )

        # 使用 graphviz 的 Source 类生成图像
        source = Source(dot_source)

        # 捕获 PNG 数据
        png_data = source.pipe(format='png')

        # 捕获 SVG 数据
        svg_data = source.pipe(format='svg')

        #pics.dot.renderer = "cairo"

    return png_data, svg_data

# 下载 SVG 路由
#@app.route('/download/svg')
#def download_svg():
#    svg_data = session.get('svg_data')
#    if svg_data:
#        return send_file(io.BytesIO(svg_data), mimetype='image/svg+xml', as_attachment=True, download_name='plot.svg')
#    return "No SVG data found."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)