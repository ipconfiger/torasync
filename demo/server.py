#coding=utf8
__author__ = 'Alexander.Li'

######################################### Notice #####################################
#
#   本文件演示了torasync的部分用法，更多的玩法期待你来提供
#
######################################################################################


import sys
sys.path.append("../")
import tornado.ioloop
import tornado.web
from torasync import torasync


class MainHandler(tornado.web.RequestHandler):
    """
    基本不会侵入tornado框架本身，可以和tornado的框架的其他特性混用
    """
    def get(self):
        self.finish("it works!")


class SleepNSeccondHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self, n_seconds):
        torasync.remote_call(self, self.sleepAndResponse, torasync.JsonResponse(), n_seconds)

    @torasync.mapping
    def sleepAndResponse(self, context, N):
        """
        这个方法实际上是执行在另外的进程里的，所以在访问全局的成员的时候要小心，全局的成员都被赋值到了子进程中，所以global后都无法同步到
        其他进程的，尽量不要写global的对象，另外 self 对象其实已经不是这个class实例本身了，这点比较魔幻，暂时没想好什么其他办法，所以
        重新定义了一个request类，把webRequest的成员一部分访问form啊body啊file啊的数据结构mock了，替换成了self放这里。
        :param context: 就是本文件中那个Context类的实例，在init_processor中返回了这个实例，会在这个地方放进来
        :param N:url的参数
        :return:返回的数据
        """
        import time
        time.sleep(float(N))
        return dict(txt="i sleep %s seconds" % N)



application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/sleep/([^/]+)", SleepNSeccondHandler),
    (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": r"./"}),
])

def timmer(handler, context):
    """
    这个进程后台会一直运行不会返回，sleep固定的时间就可以用来做一些在后台需要定期做的事情
    :param handler:
    :param context:
    :return:
    """
    import time
    while True:
        #这里放一些需要定时执行的工作
        time.sleep(1)


class Context(object):
    db_conn = None
    redis_conn = None


def init_processor():
    """
    这个方法在每个工作进程启动的时候都会先执行，用于执行在进程启动的时候的初始化工作，比如数据库连接啊，redis连接啊
    :return: 返回进程环境对象
    """
    ctx = Context()
    ctx.db_conn = None #或者连接数据库
    ctx.redis_conn = None #或者redis连接
    return ctx


if __name__ == "__main__":
    application.listen(9527)
    ioLoop = tornado.ioloop.IOLoop.instance()
    torasync.worker_start(ioLoop, init=init_processor)
    torasync.remote_task(None, timmer) #启动一个后台一直跑的进程
    ioLoop.start()