# jblib
## Author: Justin Bard

This module was written to minimize the need to write the functions I use often. 

---
The source code can be viewed here: [https://github.com/ANamelessDrake/jblib](https://github.com/ANamelessDrake/jblib)

More of my projects can be found here: [http://justbard/com](http://justbard.com)

---
```
class cd()
        
    Example: 
        with cd(directory):
            print (os.getcwd()) 

        print (os.getcwd()) ## Back at the originating directory on exit
```
---
```
class hilight(string).color(higlight=True, bold=True)

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