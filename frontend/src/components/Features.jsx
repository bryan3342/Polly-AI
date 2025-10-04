import { IoMdSettings } from "react-icons/io";
import { TiHomeOutline } from "react-icons/ti";

const Features = () => {
    return (
        <div className="flex flex-row items-center p-4 gap-2">
            <IoMdSettings className="text-gray-500 text-2xl hover:text-white cursor-pointer transition-colors" />
            <TiHomeOutline className="text-gray-500 text-2xl hover:text-white cursor-pointer transition-colors" />
        </div>
    );
}

export default Features;