#coding=utf8
__author__ = 'Alexander.Li'

import multiprocessing
import logging
import uuid
import signal
import traceback
import sys

#用来获取worker进程返回数据的队列
CALLBACK_QUEUE = multiprocessing.Queue()
#用来获取主进程发布任务的队列
DISPATCH_QUEUE = multiprocessing.Queue()
#进程池
PROCESSES = []
#处理器池
PROCESSORS = {}
#注册的后端进程方法
REGISTED_FUNCTIONS = {}
#发起的异步请求
REMOTE_CALLS = {}
#进程环境初始化函数
INIT_FUNC = None
#后端进程执行结果池
TASK_RESULTS = {}


class Request(object):
    """
    用于包装Http请求，主要原因是Tornado的request对象没有办法跨进程传输
    """
    def __init__(self, httpRequest):
        self.arguments = httpRequest.arguments
        self.body = httpRequest.body
        self.headers = dict([(k, v) for k, v in httpRequest.headers.iteritems()])
        self.cookies = httpRequest.cookies
        self.remote_ip = httpRequest.remote_ip
        self.files = httpRequest.files

    def get_argument(self, key, default=None):
        """
        获取参数列表
        :param key:key
        :param default:默认值
        :return:返回值
        """
        item = self.get_arguments(key, default=default)
        if item:
            return item[0]
        return default

    def get_arguments(self, key, default=None):
        """
        返回数组形式的参数
        :param key:key
        :param default:默认值
        :return:
        """
        if key in self.arguments:
            return self.arguments[key]
        return default


class JsonResponse(object):
    """
    直接从后端进程返回Json结果的处理器
    """
    def process(self, handler, data):
        """
        处理方法
        :param handler: tornado的webRequest对象
        :param data: 后端进程返回的json数据
        :return:
        """
        import json
        try:
            handler.set_header('Content-Type', 'application/json; charset="utf-8"')
            handler.finish(json.dumps(data))
        except:
            logging.error(u"error json format:%s", data)
            handler.finish(json.dumps({}))


class Callback(object):
    """
    执行传入的回调函数，用于自定义后续的处理方式
    """
    def __init__(self, callback):
        self.callback = callback

    def process(self, handler, data):
        """
        处理方法
        :param handler: tornado的webRequest对象
        :param data: 后端进程返回的数据
        :return:
        """
        self.callback(data)


class Render(object):
    """
    直接用指定的模板来渲染后端返回的数据
    """
    def __init__(self, template):
        self.template = template

    def process(self, handler, data):
        """
        处理器方法
        :param handler: tornado的webRequest对象
        :param data: 后端进程返回的数据
        :return:
        """
        handler.render(self.template, **data)
        handler.finish()


def mapping(func):
    """
    用于映射函数到后端进程的装饰器
    :param func:
    :return:
    """
    REGISTED_FUNCTIONS[func.func_name] = func
    return func


def worker(inQueue, outQueue):
    """
    后端进程函数
    :param inQueue:接收任务的队列
    :param outQueue:返回数据的队列
    :return:
    """
    context = INIT_FUNC() if INIT_FUNC else None
    while True:
        message = inQueue.get()
        req_id = None
        try:
            req_id, method_name, req, args = message
            if method_name in REGISTED_FUNCTIONS:
                returnValue = REGISTED_FUNCTIONS[method_name](req, context, *args)
                outQueue.put((req_id, returnValue))
        except Exception, e:
            traceback.print_exc()
            if req_id:
                outQueue.put((req_id, dict(status=False, error=u"%s" % e)))


def sendToBackground(req_id, func_name, message, *args):
    """
    发送任务到后端进程
    :param req_id:请求的编号
    :param func_name: 函数名称
    :param message: 参数数据
    :param args: 额外定义的参数
    :return:
    """
    DISPATCH_QUEUE.put_nowait((req_id, func_name, message, args))


def remote_call(handler, remote_method, processer,  *args):
    """
    发起要返回的后端请求
    :param handler: tornado的webRequest，一般来说是self
    :param remote_method: 要执行的任务定义的函数，这个函数在后端进程执行，小心调用公共区域的成员
    :param processer: 处理器的对象
    :param args: 额外的参数
    :return:
    """
    request_id = uuid.uuid4().hex
    REMOTE_CALLS[request_id] = handler
    PROCESSORS[request_id] = processer
    sendToBackground(request_id, remote_method.func_name, Request(handler.request), *args)


def remote_task(handler, remote_method, *args):
    """
    发起不需要立即返回的后端请求
    :param handler:tornado的webRequest，一般来说是self
    :param remote_method:要执行的任务定义的函数，这个函数在后端进程执行，小心调用公共区域的成员
    :param args:额外的参数
    :return:返回请求的唯一ID
    """
    request_id = uuid.uuid4().hex
    sendToBackground(request_id, remote_method.func_name, Request(handler.request) if handler else None, *args)
    return request_id


def try_task(req_id):
    """
    尝试remote_task的返回值
    :param req_id:
    :return: 返回请求的执行结果
    """
    global TASK_RESULTS
    if req_id in TASK_RESULTS:
        rep = TASK_RESULTS[req_id]
        if rep:
            del TASK_RESULTS[req_id]
            return rep
    return None


def onSignal(signalnum, stack):
    """
    当主进程收到kill信号量的时候清除所有的子进程
    :param signalnum:
    :param stack:
    :return:
    """
    for process in PROCESSES:
        try:
            process.terminate()
        except:
            pass
    sys.exit(1)


def worker_start(ioLoop, init=None, process_count=0):
    """
    开启后端worker进程
    :param ioLoop: tornado的ioloop对象
    :param init: 所有进程的初始化环境函数，用于比如统一连接数据库之类的事情
    :param process_count: 后端进程的数量，不设置的话默认开启cpu数量的2倍
    :return:
    """
    def callback(*args):
        """
        每次ioloop尝试获取后端返回队列的数据
        :param args:
        :return:
        """
        global TASK_RESULTS, REMOTE_CALLS, PROCESSORS
        if not CALLBACK_QUEUE.empty():
            message = CALLBACK_QUEUE.get(False)
            try:
                global REMOTE_CALLS
                req_id, response = message
                if req_id in REMOTE_CALLS and req_id in PROCESSORS:
                    try:
                        procesor = PROCESSORS[req_id]
                        procesor.process(REMOTE_CALLS[req_id], response)
                    except:
                        traceback.print_exc()
                    del REMOTE_CALLS[req_id]
                    del PROCESSORS[req_id]
                else:
                    TASK_RESULTS[req_id] = response
            except:
                traceback.print_exc()
            logging.info("callback message:%s", message)
        ioLoop.add_callback(callback)
    callback()
    signal.signal(signal.SIGTERM, onSignal)
    global PROCESSES
    global INIT_FUNC
    INIT_FUNC = init
    if process_count<1:
        process_count = multiprocessing.cpu_count()
    for i in range(process_count):
        process = multiprocessing.Process(target=worker, name="P-%s" % i, args=(DISPATCH_QUEUE, CALLBACK_QUEUE))
        process.start()
        PROCESSES.append(process)
    logging.info("sub processes started!!")

