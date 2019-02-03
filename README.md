# jblib
## Author: Justin Bard

This module was written to minimize the need to write the functions I use often.

INSTALL:  ` python3 -m pip install jblib `

---
The source code can be viewed here: [https://github.com/ANamelessDrake/jblib](https://github.com/ANamelessDrake/jblib)

More of my projects can be found here: [http://justbard/com](http://justbard.com)

---
` import jblib `
```
    class cd()
            
        Example: 
            with cd(directory):
                print (os.getcwd()) 

            print (os.getcwd()) ## Back at the originating directory on exit
```

```
    class hilight(string).color(highlight=True, bold=True)

        Example:
            print (hilight("Hello World").red(bold=True))

            Or you could make an object:
                text = hilight("Bar")

                print ("Foo "+text.blue())

            To return the original string:
                print (text.string)
        
        Available Colors:
            red
            green
            yellow
            blue
            purple
            teal
            white
```
---
` import convert_module `
```
    Module to convert various data
            
            def convert_time_from_seconds(seconds_given)
                Converts a seconds into minutes, hours and days. 
            
            def IP2Int(ip)
                Converts a IPv4 address to a interger - This is useful to store IP addresses in databases
            
            def Int2IP(ipnum)
                Converts a interger back to an IPv4 address

            def urlcode(url, encode=False)
                Wrapper for urllib.parse.quote and urllib.parse.unquote.
                From urllib docs - Replace special characters in string using the %xx escape. Letters, digits, and the characters '_.-' are never quoted. By default, this function is intended for quoting the path section of URL. 
                - https://docs.python.org/3.1/library/urllib.parse.html?highlight=urllib#urllib.parse.quote
```