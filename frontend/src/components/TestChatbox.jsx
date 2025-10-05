const TestChatbox = () => {
    return (
        <div 
            className="w-[419px] h-[716px] border-[3px] border-red-500 bg-blue-500 flex items-center justify-center"
            style={{
                width: '419px',
                height: '716px',
                backgroundColor: '#3B82F6',
                border: '3px solid #EF4444',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
            }}
        >
            <h1 style={{color: 'white', fontSize: '24px', fontWeight: 'bold'}}>
                TEST CHATBOX
            </h1>
        </div>
    );
};

export default TestChatbox;