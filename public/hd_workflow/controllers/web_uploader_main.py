# -*- coding: utf-8 -*-
from jinja2 import Environment, FileSystemLoader
import os
import hashlib
from odoo import http
from odoo.http import request
import logging
import odoo



BASE_DIR = os.path.dirname(os.path.dirname(__file__))
templateLoader = FileSystemLoader(searchpath=BASE_DIR + "/static/templates")
env = Environment(loader=templateLoader)
_logger = logging.getLogger(__name__)


class webuploader_web(http.Controller):
    @http.route('/webuploader/index', type='http', auth="public", csrf=False)
    def webuploader_index(self, **post):
        """
        判断用户来源
        :param post:
        :return:
        """
        values = {}
        if post:
            if post['res_model'] == 'ir.attachment':
                data = request.env['documents.folder'].sudo().browse(int(post['res_id']))
                values['object'] = data
                values['folder_id'] = data.id
            else:
                # check = request.env['ir.attachment'].sudo()._check_create(post)
                # if check == False:
                #     return '当前单据状态下无权限上传附件!'
                data = request.env[post['res_model']].browse(int(post['res_id']))
                values['object'] = data
                values['folder_id'] = 1
            values['csrf_token'] = None
            values['res_model'] = post['res_model']
            values['res_id'] = post['res_id']
            values['type_id'] = post.get('type_id', '')
            template = env.get_template('index.html')
            html = template.render(object=values)
            return html
        else:
            return '来源出错'

    @http.route('/webuploader/upload', methods=['POST'], type='http', auth="public", csrf=False)
    def webuploader_upload(self, **post):  # 接收前端上传的一个分片
        md5 = post['fileMd5']
        chunk_id = request.httprequest.form.get('chunk', 0, type=int)
        filename = '{}-{}'.format(md5, chunk_id)
        upload_file = post['file']
        with open(BASE_DIR + '/static/upload/{}'.format(filename), 'wb+') as fdst:
            upload_file.save(fdst)
        target_filename = post['name']  # 获取上传文件的文件名
        return target_filename

    @http.route('/webuploader/checkChunk', type='http', auth="public", csrf=False)
    def webuploader_checkChunk(self, **post):
        md5 = post['fileMd5']
        chunk_id = request.httprequest.form.get('chunk', 0, type=int)
        filename = BASE_DIR + '/static/upload/{}-{}'.format(md5, chunk_id)
        if os.path.exists(filename):
            return 'True'
        else:
            return 'False'

    @http.route('/webuploader/mergeChunks', methods=['POST'], type='http', auth="public", csrf=False)
    def webuploader_mergeChunks(self, **post):
        """
        文件合并，删除上传文件，删除切片，保存到附件列表
        后期可以优化不存文件直接存内存中
        :param post:
        :return:
        """
        cr, uid, context, pool = request.cr, request.session.uid, request.context, request.env
        # guid = str(uuid.uuid4())  # 保证系统不重名
        fileName = post['fileName']  # 获取上传文件的文件名

        md5 = request.httprequest.form.get('fileMd5')
        chunk = 0  # 分片序号
        #::::系统附件存放位置
        #location = odoo.tools.config.filestore(cr.dbname.lower())

        #::::读取第一个切片
        filename = BASE_DIR + '/static/upload/{}-{}'.format(md5, chunk)
        f = open(filename, 'rb')  # 读取整包文件
        bin_data = f.read()
        f.close()  # 关闭流

        checksum = self._compute_checksum(bin_data)
        store_fname = '%s/%s' % (checksum[0:2], checksum)

        #::::附件合并后直接copy 到附件目录自动创建新的编号
        dbName = cr.dbname.lower()
        dirname = odoo.tools.config.filestore(dbName) + '/%s/%s' % (checksum[0:2], checksum)
        is_file = odoo.tools.config.filestore(dbName) + '/%s' % (checksum[0:2])
        # os.path.isdir(is_file)判断该路径是否为目录
        # os.makedirs(is_file)递归创建目录
        if not os.path.isdir(is_file):
            os.makedirs(is_file)

        #::::::上传后合并 并保存到附件目录
        bin_data_len = 0
        with open(dirname, 'wb') as target_file:  # 创建新文件
            while True:
                try:
                    if chunk == 0:
                        target_file.write(bin_data)  # 直接取第一个切片
                        chunk += 1
                        bin_data_len += len(bin_data)
                    else:
                        filename = BASE_DIR + '/static/upload/{}-{}'.format(md5, chunk)
                        if os.path.exists(filename):
                            source_file = open(filename, 'rb')  # 按序打开每个分片
                            target_file.write(source_file.read())  # 读取分片内容写入新文件
                            source_file.close()
                            chunk += 1
                        else:
                            break
                    os.remove(filename)  # 删除该分片，节约空间
                except:
                    break
        if os.path.exists(dirname):
                attachment_vals = {
                    # 'mimetype': mimetype,
                    'name': fileName,
                    'res_name': fileName,
                    'store_fname': store_fname,  # 后并后 附件名称存本地的名称带/
                    'checksum': checksum,  # 后并后 附件名称存本地的名称未带/
                    'res_model': request.params.get('res_model'),
                    'res_id': request.params.get('res_id'),
                    'file_size': bin_data_len,
                    # 'datas': base64.b64encode(open(target_file.name, 'rb').read())
                }
                pool['ir.attachment'].with_context(big_attachment=True).create(attachment_vals)
        else:
            _logger.info('上传附件失败 %s', filename)
            return 'no'
        return 'ok'

    def _compute_checksum(self, bin_data):
        """ compute the checksum for the given datas
            :param bin_data : datas in its binary form
        """
        # an empty file has a checksum too (for caching)
        return hashlib.sha1(bin_data or b'').hexdigest()

    # @http.route('/file/download/<filename>', methods=['GET'])
    # def file_download(self, filename):
    #     def send_chunk():  # 流式读取
    #         store_path = './upload/%s' % filename
    #         with open(store_path, 'rb') as target_file:
    #             while True:
    #                 chunk = target_file.read(20 * 1024 * 1024)
    #                 if not chunk:
    #                     break
    #                 yield chunk

    # return Response(send_chunk(), content_type='application/octet-stream')
