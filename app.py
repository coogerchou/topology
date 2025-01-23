import base64
import datetime
import os
from flask import Flask, jsonify, render_template, request, send_file, render_template_string, session, send_from_directory
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
    #print(combinations)

    # 生成图片
    (
        core_switch_png_data, core_switch_svg_filename,
        relationship_png_data, relationship_svg_filename
    ) = generate_images(combinations)

    # 返回结果
    return jsonify({
        'status': 'success',
        'core_switch_png_image': base64.b64encode(core_switch_png_data).decode('utf-8'),  # Base64 编码的 PNG 图片
        'core_switch_svg_download_url': f'{core_switch_svg_filename}',  # 核心交换机连接图的 SVG 下载链接
        'relationship_png_image': base64.b64encode(relationship_png_data).decode('utf-8'),  # Base64 编码的 PNG 图片
        'relationship_svg_download_url': f'{relationship_svg_filename}',  # 关系图的 SVG 下载链接
    })
# 下载路由
@app.route('/<filename>')
def download(filename):
    return send_from_directory('', filename, as_attachment=True)

# 你的生成图片函数
def generate_images(user_input):
    excel_path = os.path.join('data', 'topology-entry.xlsx')
    #print(excel_path)

    def get_df(excel_path):
        # 处理数据
        df_mapping = pd.read_excel(excel_path, sheet_name='Product')
        df_mapping = df_mapping[df_mapping.columns[1:]]

        # 筛选必有的 node
        df_default = df_mapping[df_mapping['default'] == 'y']

        # 读取用户输入
        df_input_raw = pd.DataFrame(user_input, columns=['Product', 'Zone'])

        # 把用户输入的内容，基于基础库 mapping 扩展
        list_mapping_columns = df_mapping.columns.to_list()
        list_mapping_columns.remove('Zone')
        df_input = pd.merge(df_input_raw, df_mapping[list_mapping_columns], on='Product', how='left')
        df_input = pd.concat([df_input, df_default])

        # 整理选择用哪个 png
        df_input['icon-used'] = df_input[df_input['default'] != 'y']['icon-red']
        df_input['icon-used'][(df_input['default'] != 'y') & (df_input['Zone'] == '业务应用区')] = df_input['icon-blue']
        df_input['icon-used'][df_input['default'] == 'y'] = df_input['icon-blue']

        list_special_product = [
            ('EDR-red.png', '电脑', 'desktop-EDR.png'),
            ('EDR-red.png', '笔记本', 'laptop-EDR.png'),
            ('HostEPP-red.png', '服务器', 'server-EDR.png')
        ]

        for special_product in list_special_product:
            if special_product[0] in df_input['icon-used'].to_list():
                df_input.loc[df_input['Product'] == special_product[1], 'icon-used'] = special_product[2]

        return df_input

    df = get_df(excel_path)
    path_icon = os.path.join('static', 'custom_icon/')

    def get_relationship(df):
        relationships = []
        list_unwanted_columns = ['icon-blue', 'icon-red', 'default', 'Zone', 'Core', 'icon-used']
        list_relationships_header = [i for i in df.columns.to_list() if i not in list_unwanted_columns]
        list_product_all = df['Product'].to_list()
        df_temp = df[list_relationships_header]

        for _, row in df_temp.iterrows():  # 遍历每一行
            sender = row["Product"]  # 获取 node_a
            for receiver, label in row.items():  # 遍历每一列
                if receiver == "Product":  # 跳过 "Node" 列
                    continue
                if str(label) != 'nan' and sender != receiver and receiver in list_product_all:
                    relationships.append((sender, receiver, label, {}))
        return relationships

    relationships = get_relationship(df)
    print(relationships)

    global_node_attrs = {
        "fontsize": "11",  # 字体大小
        "width": "0.9",    # 节点宽度
        "height": "0.9",   # 节点高度
        "fixedsize": "true"  # 固定大小
    }

    graph_attrs = {
        "size": "12,12",  # 图表的最大尺寸 (宽度, 高度) 单位为英寸
        "dpi": "500",     # 每英寸点数，影响图像质量
        "ratio": "0.9",   # 自动调整比例以适应给定的 size
        "rankdir": "LR"   # 从左到右布局
    }

    edge_attrs = {
        'fontsize':'10',
        'fontcolor':'red'
    }

    def draw_element(df, name_zone, is_visible='visible', group_size=2):
        df_temp = df[df['Zone'] == name_zone]
        list_product = df_temp['Product'].to_list()
        list_icon_used = df_temp['icon-used'].to_list()

        list_product_sec = df[df['Zone'] == '安全管理区']['Product'].to_list()

        nodes_cluster = {}
        for i in range(len(list_product)):
            nodes_cluster.update(
                {list_product[i]: Custom(list_product[i], path_icon + list_icon_used[i])}
            )

        # 将节点分组，每组最多 group_size 个节点
        groups = [list_product[i:i + group_size] for i in range(0, len(list_product), group_size)]

        #if name_zone in ['安全管理区']:
        #    print('groups:', groups)
            # 在每组内部横向排列节点
        #    for group in groups:
        #        for i in range(1, len(group)):
        #            nodes_cluster[group[i]] - Edge(style='invis', constraints='false') - nodes_cluster[group[i - 1]]

            # 在组与组之间纵向排列
        #    for i in range(1, len(groups)):
        #        nodes_cluster[groups[i][0]] - Edge(style='invis', constraints='false') - nodes_cluster[groups[i - 1][0]]
        
        # 对电脑和服务器，横向连接
        list_zone_lateral = ['业务应用区', '园区网']
        if len(list_product_sec) > 2:
            list_zone_lateral = list_zone_lateral + ['交换区','DMZ']
        if name_zone in list_zone_lateral: #, '交换区', 'DMZ'
            for i in range(len(list_product)):
                if i > 0:
                    nodes_cluster[list_product[i]] - Edge(style='invis', constraints='false') - nodes_cluster[list_product[i - 1]]

        return nodes_cluster

    # 生成第一张图：所有节点连接到“核心交换机”
    def draw_graph(type_graph='deployment'):
        with Diagram('diagram_'+type_graph, show=False, filename=None, direction="LR", graph_attr=graph_attrs,
                    node_attr=global_node_attrs, outformat=['png','svg']) as pic:

            with Cluster('互联网'):
                internet = draw_element(df, '互联网', is_visible='invisible')

            with Cluster('企业网络'):
                with Cluster('网络周界'):
                    with Cluster('DMZ'):
                        DMZ = draw_element(df, 'DMZ', is_visible='invisible')

                with Cluster('内部网络'):
                    with Cluster('交换区'):
                        switch_secs = draw_element(df, '交换区', is_visible='invisible')

                    with Cluster('园区网'):
                        office = draw_element(df, '园区网', is_visible='visible')

                    with Cluster('数据中心'):
                        with Cluster('安全管理区'):
                            secs = draw_element(df, '安全管理区', is_visible='invisible', group_size=2)

                        with Cluster('业务应用区'):
                            servers = draw_element(df, '业务应用区', is_visible='visible')

            if type_graph == 'deployment':
                edge_style_switch = 'vis'
                edge_style_data = 'invis'
            else:
                edge_style_switch = 'invis'
                edge_style_data = 'vis'

            # 连接交换区到其他区域
            switch_secs['核心交换机'] - Edge(style=edge_style_switch) - list(office.values())
            switch_secs['核心交换机'] - Edge(style=edge_style_switch) - list(servers.values())
            switch_secs['核心交换机'] - Edge(style=edge_style_switch) - list(secs.values())
            list(DMZ.values()) - Edge(style=edge_style_switch) - switch_secs['核心交换机']
            internet['云'] - Edge(style='dashed') - DMZ['防火墙']

            # 一些特殊的强制节点，为了 layout
            DMZ['防火墙'] >> Edge(style='invis') >> list(switch_secs.values())
            list(switch_secs.values())[0] - Edge(style='invis') - list(secs.values())
            list(switch_secs.values())[0] - Edge(style='invis') - list(secs.values())
            
            if ('NGSOC-安全运营平台' in secs.keys()) and ('椒图-主机安全' not in secs.keys()):
                secs['NGSOC-安全运营平台'] - Edge(style='invis') - list(servers.values())
            if ('NGSOC-安全运营平台' in secs.keys()) and ('天擎-终端安全-EPP/EDR' not in secs.keys()):
                secs['NGSOC-安全运营平台'] - Edge(style='invis') - list(office.values())

            # 连接所有节点
            all_nodes = {**internet, **office, **servers, **secs, **switch_secs, **DMZ}
            for sender, receiver, label, edge_attrs in relationships:
                #print(sender)
                #print(all_nodes(sender))
                sender_node = all_nodes[sender]
                receiver_node = all_nodes[receiver]
                edge = Edge(xlabel=label, style=edge_style_data, fontsize='11')
                sender_node >> edge >> receiver_node
        return pic
    
    pic_deployment = draw_graph(type_graph='deployment')
    pic_data = draw_graph(type_graph='dataflow')

    # 获取生成的 DOT 源码
    deployment_dot_source = str(pic_deployment)
    dataflow_dot_source = str(pic_data)

    # 使用 graphviz 的 Source 类生成图像
    deployment_source = Source(deployment_dot_source)
    dataflow_source = Source(dataflow_dot_source)

    # 捕获 PNG 数据
    deployment_png_data = deployment_source.pipe(format='png')
    dataflow_png_data = dataflow_source.pipe(format='png')

    # 生成 SVG 文件
    deployment_svg_filename = 'diagram_deployment.svg'
    dataflowt_svg_filename = 'diagram_dataflow.svg'

    def generate_svg(svg_filename):
        svg_path = os.path.join('', svg_filename)
        with open(svg_path, "rt") as f:
            in_string = f.read()
            out_string = scour.scourString(in_string) #, options

        with open(svg_path, "wt") as f:
            f.write(out_string)
    
    generate_svg(deployment_svg_filename)
    generate_svg(dataflowt_svg_filename)
    

    return (
        deployment_png_data, deployment_svg_filename,
        dataflow_png_data, dataflowt_svg_filename
    )

# 下载 SVG 路由
#@app.route('/download/svg')
#def download_svg():
#    svg_data = session.get('svg_data')
#    if svg_data:
#        return send_file(io.BytesIO(svg_data), mimetype='image/svg+xml', as_attachment=True, download_name='plot.svg')
#    return "No SVG data found."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
    #app.run(debug=True)