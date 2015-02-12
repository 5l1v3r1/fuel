# fuel

Fuel provides your machine learning models with the data they need to learn.

* Interfaces to common datasets such as MNIST, CIFAR-10 (image datasets), Google's One Billion Words (text), and many more
* The ability to iterate over your data in a variety of ways, such as in minibatches with shuffled/sequential examples
* A pipeline of preprocessors that allow you to edit your data on-the-fly, for example by adding noise, extracting n-grams from sentences, extracting patches from images, etc.

Fuel is developed primarily for use by [Blocks](http://github.com/bartvm/fuel), a Theano toolkit that helps you train neural networks.
