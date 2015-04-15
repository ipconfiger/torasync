# torasync
Run task asynchronously in other processes in easy way

>很多人在第一次接触tornado的同学都会面临一个问题。tornado的本身提供的异步封装只包括了http请求的封装，那么当我们在使用tornado构建一些复杂逻辑的时候
>会非常的烧脑。异步的语法会传染，哪怕是tornado提供了对yield的支持，但是大多数的py库都没有提供对此的支持。所以这次一不做二不休，干脆就一次性把复杂的
>耗时操作一次性放到自己维护的一堆进程里去执行，再异步的返回执行的结果。

## 安装

>sudo pip install torasync


## 使用

详见 demo，内有详细注释，本体代码不超过300行，欲知详情RTFC吧