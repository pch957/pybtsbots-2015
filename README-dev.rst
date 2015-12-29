=========================
trade bots for bitshares
=========================

.. image:: https://bitsharestalk.org/BitSharesFinalTM200.png
   :target: https://bitsharestalk.org

This project provides trade bots for bitshares

Project Setup
=============

Instructions
------------
#. Clone the project ::

        git clone git@github.com:pch957/btsbots.git
        cd btsbots

#. Install the project's development and runtime requirements::

        sudo pip3 install -r requirements-dev.txt

#. Install ``argparse`` package when developing for Python 2.6::

        sudo pip3 install argparse

#. Run the tests::

        paver test_all

   You should see output similar to this::

       $ paver test_all
       ---> pavement.test_all
       No style errors
       ========================================================================= test session starts ==========================================================================
       platform linux2 -- Python 2.7.3[pypy-2.2.1-final] -- pytest-2.5.1
       collected 7 items 

       tests/test_main.py .......

       ======================================================================= 7 passed in 0.59 seconds =======================================================================
         ___  _   ___ ___ ___ ___
        | _ \/_\ / __/ __| __|   \
        |  _/ _ \\__ \__ \ _|| |) |
        |_|/_/ \_\___/___/___|___/

   The substitution performed is rather naive, so some style errors may be reported if the description or name cause lines to be too long. Correct these manually before moving to the next step. If any unit tests fail to pass, please report an issue.

#. build and install::

        paver build
        sudo paver install

Supported Python Versions
=========================

supports the following versions out of the box:

* CPython 2.6, 2.7, 3.3
* PyPy 1.9

CPython 3.0-3.2 may also work but are at this point unsupported. PyPy 2.0.2 is known to work but is not run on Travis-CI.

Jython_ and IronPython_ may also work, but have not been tested. If there is interest in support for these alternative implementations, please open a feature request!

.. _Jython: http://jython.org/
.. _IronPython: http://ironpython.net/

Licenses
========
The code which makes up this project is licensed under the MIT/X11 license. Feel free to use it in your free software/open-source or proprietary projects.

Issues
======

Please report any bugs or requests that you have using the GitHub issue tracker!

Authors
=======

* Alt
